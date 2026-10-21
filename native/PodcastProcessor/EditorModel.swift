import AVFoundation
import CoreGraphics
import CoreVideo
import ImageIO
import SwiftUI
import UniformTypeIdentifiers

#if os(macOS)
import AppKit
typealias PlatformImage = NSImage
#else
import UIKit
typealias PlatformImage = UIImage
#endif

struct PictureItem: Identifiable, Equatable {
    let id: String
    var name: String
    var image: CGImage
    var x: Double
    var y: Double
    var scale: Double
}

struct PersonItem: Identifiable {
    let id: String
    var name: String
    var body: CGImage
    var mouths: [String: CGImage]
    var isOn: Bool
    var audioName: String?
    var levels: [Float] = []
}

enum EditLayer {
    case foreground
    case background
}

@Observable
final class EditorModel {
    static let scene = CGSize(width: 1280, height: 720)
    static let shapes = ["closed", "small", "medium", "wide", "round", "teeth"]

    var people: [PersonItem] = []
    var backgrounds: [PictureItem] = []
    var foregrounds: [PictureItem] = []
    var backgroundID = "coffee"
    var foregroundID = "none"
    var editLayer: EditLayer = .background
    var time: TimeInterval = 0
    var note: String?
    private var players: [String: AVAudioPlayer] = [:]

    private var dragStart: CGPoint?
    private var dragOrigin: (x: Double, y: Double, scale: Double)?
    private var resizing = false

    init() {
        let names = [
            ("adam", "Adam"),
            ("ben", "Ben"),
            ("corey", "Corey"),
            ("emily", "Emily"),
            ("abby-r", "Abby R"),
            ("abby-s", "Abby S"),
        ]
        people = names.compactMap { id, name in
            guard let body = Self.bundleImage("person-\(id)", ext: "png") else { return nil }
            var mouths: [String: CGImage] = [:]
            for shape in Self.shapes {
                if let image = Self.bundleImage("mouth-\(id)-\(shape)", ext: "png") {
                    mouths[shape] = image
                }
            }
            return PersonItem(id: id, name: name, body: body, mouths: mouths, isOn: true)
        }
        if let coffee = Self.bundleImage("coffee-shop", ext: "jpg") {
            backgrounds.append(PictureItem(id: "coffee", name: "Coffee shop", image: coffee, x: 50, y: 50, scale: 100))
        }
        if let library = Self.bundleImage("library", ext: "jpg") {
            backgrounds.append(PictureItem(id: "library", name: "Library", image: library, x: 50, y: 50, scale: 100))
        }
        if backgrounds.isEmpty == false {
            backgroundID = backgrounds[0].id
        }
    }

    var background: PictureItem? {
        backgrounds.first { $0.id == backgroundID }
    }

    var foreground: PictureItem? {
        foregrounds.first { $0.id == foregroundID }
    }

    func chooseBackground(_ id: String) {
        backgroundID = id
        editLayer = .background
    }

    func chooseForeground(_ id: String) {
        foregroundID = id
        editLayer = .foreground
    }

    func addImage(data: Data, name: String, layer: EditLayer) {
        guard let image = Self.image(from: data) else {
            note = "That file is not a picture this app can use."
            return
        }
        let item = PictureItem(
            id: UUID().uuidString,
            name: name,
            image: image,
            x: 50,
            y: layer == .foreground ? 62 : 50,
            scale: layer == .foreground ? 46 : 100
        )
        if layer == .foreground {
            foregrounds.append(item)
            foregroundID = item.id
            editLayer = .foreground
        } else {
            backgrounds.append(item)
            backgroundID = item.id
            editLayer = .background
        }
    }

    func drag(to point: CGPoint) {
        if dragStart == nil {
            beginDrag(at: point)
        }
        updateDrag(to: point)
    }

    func beginDrag(at point: CGPoint) {
        guard let current = activePlacement() else { return }
        resizing = handleRect().contains(point)
        dragStart = point
        dragOrigin = (current.x, current.y, current.scale)
    }

    func updateDrag(to point: CGPoint) {
        guard let start = dragStart, let origin = dragOrigin else { return }
        let dx = Double((point.x - start.x) / Self.scene.width) * 100
        let dy = Double((point.y - start.y) / Self.scene.height) * 100
        if resizing {
            let limit = editLayer == .foreground ? 8.0...180.0 : 40.0...250.0
            setActive(x: origin.x, y: origin.y, scale: min(limit.upperBound, max(limit.lowerBound, origin.scale + dx)))
        } else {
            setActive(x: origin.x + dx, y: origin.y + dy, scale: origin.scale)
        }
    }

    func endDrag() {
        dragStart = nil
        dragOrigin = nil
        resizing = false
    }

    func frame(at time: TimeInterval) -> CGImage? {
        let width = Int(Self.scene.width)
        let height = Int(Self.scene.height)
        guard let ctx = CGContext(
            data: nil,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: 0,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else { return nil }
        let canvas = Self.scene
        ctx.setFillColor(CGColor(srgbRed: 0.11, green: 0.14, blue: 0.13, alpha: 1))
        ctx.fill(CGRect(origin: .zero, size: canvas))
        ctx.saveGState()
        ctx.clip(to: CGRect(origin: .zero, size: canvas))
        if let background {
            ctx.draw(background.image, in: placed(coverRect(background.image, centerX: background.x, centerY: background.y, scale: background.scale, canvas: canvas)))
        }
        let visible = people.filter(\.isOn)
        for (index, person) in visible.enumerated() {
            let bodyH = canvas.height * 0.72
            let bodyW = bodyH * CGFloat(person.body.width) / CGFloat(max(1, person.body.height))
            let cx = (CGFloat(index) + 0.5) / CGFloat(max(1, visible.count)) * canvas.width
            let rect = CGRect(x: cx - bodyW / 2, y: canvas.height * 0.46 - bodyH / 2, width: bodyW, height: bodyH)
            ctx.draw(person.body, in: placed(rect))
            let shape = mouthShape(person, time)
            if let mouth = person.mouths[shape] ?? person.mouths["closed"] {
                let mw = bodyW * 0.14
                let mh = mw * CGFloat(mouth.height) / CGFloat(max(1, mouth.width))
                let mouthRect = CGRect(x: rect.minX + bodyW * 0.5 - mw / 2, y: rect.minY + bodyH * 0.34, width: mw, height: mh)
                ctx.draw(mouth, in: placed(mouthRect))
            }
        }
        if let foreground {
            let fh = canvas.height * CGFloat(foreground.scale / 100)
            let fw = fh * CGFloat(foreground.image.width) / CGFloat(max(1, foreground.image.height))
            let rect = CGRect(
                x: CGFloat(foreground.x / 100) * canvas.width - fw / 2,
                y: CGFloat(foreground.y / 100) * canvas.height - fh / 2,
                width: fw,
                height: fh
            )
            let drawn = placed(rect)
            ctx.draw(foreground.image, in: drawn)
            if editLayer == .foreground {
                ctx.setStrokeColor(CGColor(srgbRed: 0.77, green: 0.36, blue: 0.15, alpha: 1))
                ctx.setLineWidth(4)
                ctx.stroke(drawn)
            }
        }
        ctx.restoreGState()
        if editLayer == .background {
            ctx.setFillColor(CGColor(srgbRed: 0.77, green: 0.36, blue: 0.15, alpha: 1))
            ctx.fill(placed(handleRect()))
        }
        return ctx.makeImage()
    }

    var hasAudio: Bool {
        people.contains { $0.isOn && !$0.levels.isEmpty }
    }

    func loadAudio(from url: URL, personID: String) {
        let allowed = url.startAccessingSecurityScopedResource()
        defer { if allowed { url.stopAccessingSecurityScopedResource() } }
        let copy = FileManager.default.temporaryDirectory.appendingPathComponent("audio-\(personID)-\(url.lastPathComponent)")
        do {
            if FileManager.default.fileExists(atPath: copy.path) {
                try FileManager.default.removeItem(at: copy)
            }
            try FileManager.default.copyItem(at: url, to: copy)
            let levels = try Self.levels(in: copy)
            let player = try AVAudioPlayer(contentsOf: copy)
            player.prepareToPlay()
            if let index = people.firstIndex(where: { $0.id == personID }) {
                people[index].levels = levels
                people[index].audioName = url.deletingPathExtension().lastPathComponent
            }
            players[personID] = player
            note = nil
        } catch {
            note = "Could not read that audio. Use a wav, mp3, or m4a file."
        }
    }

    func startAudio() {
        #if os(iOS)
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)
        #endif
        time = 0
        for person in people where person.isOn {
            guard let player = players[person.id] else { continue }
            player.currentTime = 0
            player.play()
        }
    }

    func stopAudio() {
        for player in players.values {
            player.pause()
        }
    }

    func audioFinished(_ elapsed: TimeInterval) -> Bool {
        let durations = people.filter(\.isOn).compactMap { players[$0.id]?.duration }.filter { $0 > 0 }
        guard let longest = durations.max() else { return true }
        return elapsed >= longest
    }

    private func mouthShape(_ person: PersonItem, _ time: TimeInterval) -> String {
        guard !person.levels.isEmpty else { return "closed" }
        let index = min(person.levels.count - 1, max(0, Int(time / 0.08)))
        switch person.levels[index] {
        case ..<0.06: return "closed"
        case ..<0.16: return "small"
        case ..<0.32: return "medium"
        case ..<0.50: return "round"
        case ..<0.72: return "wide"
        default: return "teeth"
        }
    }

    private static func levels(in url: URL) throws -> [Float] {
        let file = try AVAudioFile(forReading: url)
        let format = file.processingFormat
        let capacity = AVAudioFrameCount(file.length)
        guard capacity > 0, let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: capacity) else { return [] }
        try file.read(into: buffer)
        guard let channels = buffer.floatChannelData else { return [] }
        let frames = Int(buffer.frameLength)
        let hop = max(1, Int(format.sampleRate * 0.08))
        var levels: [Float] = []
        levels.reserveCapacity(frames / hop + 1)
        var index = 0
        while index < frames {
            let end = min(frames, index + hop)
            var sum: Float = 0
            for frame in index..<end {
                let sample = channels[0][frame]
                sum += sample * sample
            }
            levels.append(sqrt(sum / Float(end - index)))
            index = end
        }
        let peak = levels.max() ?? 0
        guard peak > 0.00001 else { return levels }
        return levels.map { min(1, $0 / peak) }
    }

    private func placed(_ rect: CGRect) -> CGRect {
        CGRect(x: rect.minX, y: Self.scene.height - rect.maxY, width: rect.width, height: rect.height)
    }

    func pngData() -> Data? {
        guard let image = frame(at: time) else { return nil }
        let data = NSMutableData()
        guard let dest = CGImageDestinationCreateWithData(data, UTType.png.identifier as CFString, 1, nil) else { return nil }
        CGImageDestinationAddImage(dest, image, nil)
        guard CGImageDestinationFinalize(dest) else { return nil }
        return data as Data
    }

    func writeMovie(to url: URL) throws {
        if FileManager.default.fileExists(atPath: url.path) {
            try FileManager.default.removeItem(at: url)
        }
        let writer = try AVAssetWriter(outputURL: url, fileType: .mp4)
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: 1280,
            AVVideoHeightKey: 720,
        ])
        input.expectsMediaDataInRealTime = false
        let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32BGRA),
            kCVPixelBufferWidthKey as String: 1280,
            kCVPixelBufferHeightKey as String: 720,
        ])
        writer.add(input)
        guard writer.startWriting() else { throw writer.error ?? CocoaError(.fileWriteUnknown) }
        writer.startSession(atSourceTime: .zero)
        let fps = 12
        let longest = people.filter(\.isOn).map { Double($0.levels.count) * 0.08 }.max() ?? 0
        let duration = longest > 0.2 ? longest : 4
        let frames = max(1, Int(duration * Double(fps)))
        for index in 0..<frames {
            while !input.isReadyForMoreMediaData {
                Thread.sleep(forTimeInterval: 0.002)
            }
            let sample = Double(index) / Double(fps)
            guard let image = frame(at: sample), let buffer = pixelBuffer(from: image) else { continue }
            let time = CMTime(value: CMTimeValue(index), timescale: CMTimeScale(fps))
            if !adaptor.append(buffer, withPresentationTime: time) {
                throw writer.error ?? CocoaError(.fileWriteUnknown)
            }
        }
        input.markAsFinished()
        let wait = DispatchSemaphore(value: 0)
        writer.finishWriting { wait.signal() }
        wait.wait()
        if writer.status != .completed {
            throw writer.error ?? CocoaError(.fileWriteUnknown)
        }
    }

    private func activePlacement() -> (x: Double, y: Double, scale: Double)? {
        if editLayer == .foreground {
            guard let foreground else { return nil }
            return (foreground.x, foreground.y, foreground.scale)
        }
        guard let background else { return nil }
        return (background.x, background.y, background.scale)
    }

    private func setActive(x: Double, y: Double, scale: Double) {
        if editLayer == .foreground, let index = foregrounds.firstIndex(where: { $0.id == foregroundID }) {
            foregrounds[index].x = x
            foregrounds[index].y = y
            foregrounds[index].scale = scale
        } else if let index = backgrounds.firstIndex(where: { $0.id == backgroundID }) {
            backgrounds[index].x = x
            backgrounds[index].y = y
            backgrounds[index].scale = scale
        }
    }

    private func handleRect() -> CGRect {
        CGRect(x: Self.scene.width - 56, y: Self.scene.height - 56, width: 36, height: 36)
    }

    private func coverRect(_ image: CGImage, centerX: Double, centerY: Double, scale: Double, canvas: CGSize) -> CGRect {
        let fit = max(canvas.width / CGFloat(image.width), canvas.height / CGFloat(image.height)) * CGFloat(scale / 100)
        let w = CGFloat(image.width) * fit
        let h = CGFloat(image.height) * fit
        return CGRect(
            x: CGFloat(centerX / 100) * canvas.width - w / 2,
            y: CGFloat(centerY / 100) * canvas.height - h / 2,
            width: w,
            height: h
        )
    }

    private func pixelBuffer(from image: CGImage) -> CVPixelBuffer? {
        var buffer: CVPixelBuffer?
        let options = [
            kCVPixelBufferCGImageCompatibilityKey: true,
            kCVPixelBufferCGBitmapContextCompatibilityKey: true,
        ] as CFDictionary
        CVPixelBufferCreate(kCFAllocatorDefault, image.width, image.height, kCVPixelFormatType_32BGRA, options, &buffer)
        guard let buffer else { return nil }
        CVPixelBufferLockBaseAddress(buffer, [])
        defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
        guard let ctx = CGContext(
            data: CVPixelBufferGetBaseAddress(buffer),
            width: image.width,
            height: image.height,
            bitsPerComponent: 8,
            bytesPerRow: CVPixelBufferGetBytesPerRow(buffer),
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGBitmapInfo.byteOrder32Little.rawValue | CGImageAlphaInfo.premultipliedFirst.rawValue
        ) else { return nil }
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: image.width, height: image.height))
        return buffer
    }

    private static func bundleImage(_ name: String, ext: String) -> CGImage? {
        guard let url = Bundle.main.url(forResource: name, withExtension: ext),
              let data = try? Data(contentsOf: url) else { return nil }
        return image(from: data)
    }

    private static func image(from data: Data) -> CGImage? {
        #if os(macOS)
        guard let image = NSImage(data: data) else { return nil }
        var rect = CGRect(origin: .zero, size: image.size)
        return image.cgImage(forProposedRect: &rect, context: nil, hints: nil)
        #else
        return UIImage(data: data)?.cgImage
        #endif
    }
}

struct PNGFile: FileDocument {
    static var readableContentTypes: [UTType] { [.png] }
    var data: Data
    init(data: Data) { self.data = data }
    init(configuration: ReadConfiguration) throws {
        data = configuration.file.regularFileContents ?? Data()
    }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        FileWrapper(regularFileWithContents: data)
    }
}

struct MovieFile: FileDocument {
    static var readableContentTypes: [UTType] { [.mpeg4Movie] }
    var url: URL
    init(url: URL) { self.url = url }
    init(configuration: ReadConfiguration) throws { throw CocoaError(.fileReadUnknown) }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        try FileWrapper(url: url, options: .immediate)
    }
}
