#import "MimirEngine.h"
#include <stdexcept>
#include <iostream>
#include <climits>
#include <cstdlib>
#include <string>

static void require(bool value, const char * message) { if (!value) { throw std::runtime_error(message); } }
static void wait_for(BOOL & done) {
    NSDate * deadline = [NSDate dateWithTimeIntervalSinceNow:180];
    while (!done && deadline.timeIntervalSinceNow > 0) {
        [[NSRunLoop mainRunLoop] runMode:NSDefaultRunLoopMode beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.01]];
    }
    require(done, "callback timed out");
}
int main(int argc, const char ** argv) {
    @autoreleasepool {
        try {
            require(argc == 2 || argc == 3, "provide a Mimir GGUF path and optional exit scenario");
            const std::string scenario = argc == 3 ? argv[2] : "";
            MimirEngine * engine = [MimirEngine new];
            __block BOOL done = NO;
            __block NSString * failure = nil;
            NSDictionary * profile = @{@"minimumContext":@1024, @"maximumContext":@32768,
                @"contextTiers":@[@1024, @2048, @4096, @8192, @16384, @32768],
                @"memoryFraction":@0.7, @"fixedMemoryBytes":@(256ULL*1024*1024),
                @"memoryBytesPerToken":@(2ULL*1024*1024), @"cpuAttentionBytesPerTokenSquared":@96,
                @"threads":@4, @"systemPrompt":@"Answer in the user's language."};
            [engine loadModel:@(argv[1]) context:INT_MAX useGPU:YES profile:profile completion:^(NSString * error, int loadedContext, int trainingContext) {
                failure = error; done = YES;
            }];
            wait_for(done); require(failure != nil, "unsafe allocation must be rejected");
            done = NO;
            NSMutableDictionary * smallProfile = [profile mutableCopy];
            smallProfile[@"maximumContext"] = @1024;
            smallProfile[@"contextTiers"] = @[@1024];
            [engine loadModel:@(argv[1]) context:0 useGPU:YES profile:smallProfile completion:^(NSString * error, int loadedContext, int trainingContext) {
                require(error || (loadedContext == 1024 && trainingContext == 4096), "profile tiers and GGUF training context");
                failure = error; done = YES;
            }];
            if (scenario == "exit-loading") {
                __block BOOL closed = NO;
                [engine shutdownWithCompletion:^{ closed = YES; }];
                wait_for(closed); require(done && !failure, "shutdown must drain pending load");
                CFRetain((__bridge CFTypeRef)engine); // Match SwiftUI ownership remaining alive at exit.
                std::cout << "Shutdown: pending load drained before process exit\n" << std::flush;
                std::exit(0);
            }
            wait_for(done); require(!failure, failure.UTF8String ?: "load");
            if (scenario == "exit-idle" || scenario == "exit-active") {
                __block BOOL closed = NO;
                __block BOOL requested = NO;
                __block BOOL replyFinished = scenario == "exit-idle";
                __block BOOL cancelledReply = NO;
                void (^close)(void) = ^{
                    if (requested) { return; }
                    requested = YES;
                    [engine shutdownWithCompletion:^{
                        require(NSThread.isMainThread && replyFinished, "shutdown completion ordering");
                        closed = YES;
                    }];
                };
                if (scenario == "exit-active") {
                    [engine reply:@"Skriv en lang historie på mindst 500 ord." history:@[] memory:nil autoCompact:YES budget:512 onCompacting:^{} onPrepared:^(int) {}
                        onToken:^(NSString *) { close(); }
                        completion:^(NSString * error, BOOL cancelled, BOOL limited, NSDictionary * memory) {
                            require(!error, "reply failed before shutdown");
                            cancelledReply = cancelled; replyFinished = YES;
                        }];
                } else { close(); }
                wait_for(closed);
                require(scenario == "exit-idle" || cancelledReply, "shutdown must cancel active generation");
                CFRetain((__bridge CFTypeRef)engine); // Intentional process-lifetime owner, not an ordinary scope test.
                std::cout << "Shutdown: " << scenario << " clean process exit with retained engine\n" << std::flush;
                std::exit(0);
            }

            __block int emptyCount = -1;
            done = NO;
            [engine countContext:@[] memory:nil completion:^(int tokens) { emptyCount = tokens; done = YES; }];
            wait_for(done); require(emptyCount >= 0, "empty context must have a valid count");
            NSString * prompt = @"Svar med ét ord: Hvad er 2 + 2?";
            __block NSMutableString * text = [NSMutableString new];
            done = NO;
            [engine reply:prompt history:@[] memory:nil autoCompact:YES budget:8 onCompacting:^{} onPrepared:^(int) {} onToken:^(NSString * piece) {
                require(NSThread.isMainThread, "stream callback must run on main"); [text appendString:piece];
            } completion:^(NSString * error, BOOL cancelled, BOOL limited, NSDictionary * memory) {
                failure = error; require(!cancelled, "unexpected cancellation"); done = YES;
            }];
            wait_for(done); require(!failure && text.length, "first response failed");
            NSArray * history = @[@{@"role":@"user", @"content":prompt}, @{@"role":@"assistant", @"content":[text copy]}];
            NSString * previous = nil;
            for (int repeat = 0; repeat < 2; ++repeat) {
                done = NO; text = [NSMutableString new];
                [engine reply:@"Og 3 + 3?" history:history memory:nil autoCompact:YES budget:8 onCompacting:^{} onPrepared:^(int) {} onToken:^(NSString * piece) { [text appendString:piece]; }
                  completion:^(NSString * error, BOOL cancelled, BOOL limited, NSDictionary * memory) { failure = error; done = YES; }];
                wait_for(done); require(!failure && text.length, "restored response failed");
                if (previous) { require([previous isEqualToString:text], "restored continuation differs"); }
                previous = [text copy];
            }
            done = NO; __block BOOL wasCancelled = NO;
            [engine reply:@"Skriv en lang historie." history:@[] memory:nil autoCompact:YES budget:128 onCompacting:^{} onPrepared:^(int) {} onToken:^(NSString *) {}
              completion:^(NSString * error, BOOL cancelled, BOOL limited, NSDictionary * memory) { failure = error; wasCancelled = cancelled; done = YES; }];
            [engine cancel]; wait_for(done); require(wasCancelled && !failure, "cancel-before-start failed");
            done = NO;
            [engine reply:prompt history:@[@{@"role":@"assistant", @"content":@"bad history"}] memory:nil autoCompact:YES budget:8 onCompacting:^{} onPrepared:^(int) {} onToken:^(NSString *) {}
              completion:^(NSString * error, BOOL cancelled, BOOL limited, NSDictionary * memory) { failure = error; done = YES; }];
            wait_for(done); require(failure != nil, "invalid transcript accepted");
            done = NO; text = [NSMutableString new];
            [engine reply:prompt history:@[] memory:nil autoCompact:YES budget:8 onCompacting:^{} onPrepared:^(int) {} onToken:^(NSString * piece) { [text appendString:piece]; }
              completion:^(NSString * error, BOOL cancelled, BOOL limited, NSDictionary * memory) { failure = error; done = YES; }];
            wait_for(done); require(!failure && text.length, "error/cancel recovery failed");
            NSMutableArray * longHistory = [NSMutableArray new];
            for (int i = 0; i < 30; ++i) {
                [longHistory addObject:@{@"role":@"user", @"content":
                    [NSString stringWithFormat:@"Vi planlægger tur nummer %d til Odense. Vi rejser med tog, spiser frokost klokken tolv og besøger museet bagefter. Husk at vi foretrækker vegetarisk mad.", i]}];
                [longHistory addObject:@{@"role":@"assistant", @"content":@"Jeg husker planen: tog til Odense, vegetarisk frokost klokken tolv og derefter museet."}];
            }
            __block NSDictionary * compacted = nil;
            __block BOOL summarized = NO;
            __block BOOL preparedReply = NO;
            done = NO;
            [engine reply:@"Hvilken mad foretrækker vi?" history:longHistory memory:nil autoCompact:YES budget:8
              onCompacting:^{ summarized = YES; } onPrepared:^(int tokens) {
                require(summarized && tokens > 0 && tokens <= 1024, "prepared phase follows compaction with bounded input count");
                preparedReply = YES;
              }
              onToken:^(NSString *) {}
              completion:^(NSString * error, BOOL cancelled, BOOL limited, NSDictionary * memory) {
                failure = error; compacted = memory; done = YES;
              }];
            wait_for(done); require(!failure && summarized && preparedReply && [compacted[@"covered"] intValue] > 0,
                failure.UTF8String ?: "long history must compact");
            __block int fullCount = -1;
            __block int compactCount = -1;
            done = NO;
            [engine countContext:longHistory memory:nil completion:^(int tokens) { fullCount = tokens; done = YES; }];
            wait_for(done); done = NO;
            [engine countContext:longHistory memory:compacted completion:^(int tokens) { compactCount = tokens; done = YES; }];
            wait_for(done);
            require(fullCount > 1024 && compactCount > 0 && compactCount < fullCount, "context count respects summary and off mode");
            require(longHistory.count == 60 && [compacted[@"summary"] length] > 0, "preserve original transcript");
            done = NO;
            [engine reply:@"Hvor skal vi hen?" history:longHistory memory:compacted autoCompact:YES budget:8
              onCompacting:^{} onPrepared:^(int) {} onToken:^(NSString *) {}
              completion:^(NSString * error, BOOL, BOOL, NSDictionary *) { failure = error; done = YES; }];
            wait_for(done); require(!failure, "saved summary must support continuation");
            done = NO;
            [engine reply:prompt history:longHistory memory:compacted autoCompact:NO budget:8
              onCompacting:^{ throw std::runtime_error("disabled compaction ran"); } onPrepared:^(int) {} onToken:^(NSString *) {}
              completion:^(NSString * error, BOOL, BOOL, NSDictionary *) { failure = error; done = YES; }];
            wait_for(done); require(failure != nil, "disabled compaction must use full history");
            done = NO; wasCancelled = NO;
            [engine reply:prompt history:longHistory memory:nil autoCompact:YES budget:8
              onCompacting:^{ [engine cancel]; } onPrepared:^(int) {} onToken:^(NSString *) {}
              completion:^(NSString * error, BOOL cancelled, BOOL, NSDictionary * memory) {
                failure = error; wasCancelled = cancelled;
                require(memory == nil, "cancelled compaction must not commit memory"); done = YES;
              }];
            wait_for(done); require(!failure && wasCancelled, "cancel while summarizing");
            std::cout << "Compaction: long templated history, summary continuation, disabled mode and cancellation passed\n";
            done = NO;
            [engine shutdownWithCompletion:^{ done = YES; }];
            wait_for(done);
            done = NO;
            [engine loadModel:@(argv[1]) context:1024 useGPU:YES profile:profile
                completion:^(NSString * error, int, int) { failure = error; done = YES; }];
            wait_for(done); require(failure != nil, "shutdown must reject new work");
            done = NO;
            [engine shutdownWithCompletion:^{ done = YES; }];
            wait_for(done);
            std::cout << "Bridge: Metal load, real templated generation, main callbacks, transcript restore, cancellation and recovery passed\n";
            return 0;
        } catch (const std::exception & error) { std::cerr << error.what() << '\n'; return 1; }
    }
}
