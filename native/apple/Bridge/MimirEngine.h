#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN
// Methods are called from the main thread. Work is serialized off the UI thread;
// cancel is the only concurrent runtime operation. All callbacks return on main.
@interface MimirEngine : NSObject
- (void)loadModel:(NSString *)path
         context:(int)context
          useGPU:(BOOL)useGPU
         profile:(NSDictionary<NSString *, id> *)profile
      completion:(void (^)(NSString * _Nullable error, int loadedContext, int trainingContext))completion;
- (void)reply:(NSString *)prompt
     history:(NSArray<NSDictionary<NSString *, NSString *> *> *)history
      memory:(NSDictionary<NSString *, id> * _Nullable)memory
 autoCompact:(BOOL)autoCompact
      budget:(int)budget
 onCompacting:(void (^)(void))onCompacting
     onToken:(void (^)(NSString * text))onToken
  completion:(void (^)(NSString * _Nullable error, BOOL cancelled, BOOL limitReached, NSDictionary<NSString *, id> * _Nullable memory))completion;
- (void)cancel;
// Terminal operation: cancel, drain the worker and release model resources before exit.
- (void)shutdownWithCompletion:(void (^)(void))completion NS_SWIFT_NAME(shutdown(completion:));
@end
NS_ASSUME_NONNULL_END
