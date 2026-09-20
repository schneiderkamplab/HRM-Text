Pod::Spec.new do |s|
  s.name = 'mimir_native'
  s.version = '0.1.0'
  s.summary = 'Shared on-device Mimir inference engine'
  s.description = 'C ABI for patched llama.cpp with PrefixLM and streamed compaction.'
  s.homepage = 'https://github.com/schneiderkamplab/HRM-Text'
  s.license = { :type => 'Apache-2.0' }
  s.author = { 'Danish Foundation Models' => 'https://github.com/schneiderkamplab' }
  s.source = { :path => '.' }
  s.source_files = 'Classes/**/*'
  s.vendored_frameworks = 'Frameworks/MimirRuntime.xcframework'
  s.osx.deployment_target = '14.0'
  s.ios.deployment_target = '17.0'
end
