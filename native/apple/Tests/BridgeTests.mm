#import "MimirEngine.h"
#include <stdexcept>
#include <iostream>
#include <climits>

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
            require(argc == 2, "provide a Mimir GGUF path");
            MimirEngine * engine = [MimirEngine new];
            __block BOOL done = NO;
            __block NSString * failure = nil;
            const int recommended = [MimirEngine recommendedContextWithUseGPU:YES modelBytes:1200ULL * 1024 * 1024];
            require(recommended >= 1024 && recommended <= 8192, "bounded memory defaults");
            [engine loadModel:@(argv[1]) context:INT_MAX useGPU:YES completion:^(NSString * error, int loadedContext) {
                failure = error; done = YES;
            }];
            wait_for(done); require(failure != nil, "unsafe allocation must be rejected");
            done = NO;
            [engine loadModel:@(argv[1]) context:1024 useGPU:YES completion:^(NSString * error, int loadedContext) {
                failure = error; done = YES;
            }];
            wait_for(done); require(!failure, failure.UTF8String ?: "load");
            NSString * prompt = @"Svar med ét ord: Hvad er 2 + 2?";
            __block NSMutableString * text = [NSMutableString new];
            done = NO;
            [engine reply:prompt history:@[] budget:8 onToken:^(NSString * piece) {
                require(NSThread.isMainThread, "stream callback must run on main"); [text appendString:piece];
            } completion:^(NSString * error, BOOL cancelled, BOOL limited) {
                failure = error; require(!cancelled, "unexpected cancellation"); done = YES;
            }];
            wait_for(done); require(!failure && text.length, "first response failed");
            NSArray * history = @[@{@"role":@"user", @"content":prompt}, @{@"role":@"assistant", @"content":[text copy]}];
            NSString * previous = nil;
            for (int repeat = 0; repeat < 2; ++repeat) {
                done = NO; text = [NSMutableString new];
                [engine reply:@"Og 3 + 3?" history:history budget:8 onToken:^(NSString * piece) { [text appendString:piece]; }
                  completion:^(NSString * error, BOOL cancelled, BOOL limited) { failure = error; done = YES; }];
                wait_for(done); require(!failure && text.length, "restored response failed");
                if (previous) { require([previous isEqualToString:text], "restored continuation differs"); }
                previous = [text copy];
            }
            done = NO; __block BOOL wasCancelled = NO;
            [engine reply:@"Skriv en lang historie." history:@[] budget:128 onToken:^(NSString *) {}
              completion:^(NSString * error, BOOL cancelled, BOOL limited) { failure = error; wasCancelled = cancelled; done = YES; }];
            [engine cancel]; wait_for(done); require(wasCancelled && !failure, "cancel-before-start failed");
            done = NO;
            [engine reply:prompt history:@[@{@"role":@"assistant", @"content":@"bad history"}] budget:8 onToken:^(NSString *) {}
              completion:^(NSString * error, BOOL cancelled, BOOL limited) { failure = error; done = YES; }];
            wait_for(done); require(failure != nil, "invalid transcript accepted");
            done = NO; text = [NSMutableString new];
            [engine reply:prompt history:@[] budget:8 onToken:^(NSString * piece) { [text appendString:piece]; }
              completion:^(NSString * error, BOOL cancelled, BOOL limited) { failure = error; done = YES; }];
            wait_for(done); require(!failure && text.length, "error/cancel recovery failed");
            std::cout << "Bridge: Metal load, real templated generation, main callbacks, transcript restore, cancellation and recovery passed\n";
            return 0;
        } catch (const std::exception & error) { std::cerr << error.what() << '\n'; return 1; }
    }
}
