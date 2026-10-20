import SwiftUI

@main
struct PodcastProcessorApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        #if os(macOS)
        .defaultSize(width: 1280, height: 820)
        #endif
    }
}
