#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN
// Methods are called from the main thread. Work is serialized off the UI thread;
// cancel is the only concurrent runtime operation. All callbacks return on main.
@interface MimirEngine : NSObject
+ (int)recommendedContextWithUseGPU:(BOOL)useGPU modelBytes:(uint64_t)modelBytes
    NS_SWIFT_NAME(recommendedContext(useGPU:modelBytes:));
- (void)loadModel:(NSString *)path
         context:(int)context
          useGPU:(BOOL)useGPU
      completion:(void (^)(NSString * _Nullable error, int loadedContext))completion;
- (void)reply:(NSString *)prompt
     history:(NSArray<NSDictionary<NSString *, NSString *> *> *)history
      budget:(int)budget
     onToken:(void (^)(NSString * text))onToken
  completion:(void (^)(NSString * _Nullable error, BOOL cancelled, BOOL limitReached))completion;
- (void)cancel;
@end
NS_ASSUME_NONNULL_END
