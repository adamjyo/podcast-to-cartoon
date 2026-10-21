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
    var x: Double
    var y: Double
    var scale: Double
    var mouthX: Double
    var mouthY: Double
    var mouthScale: Double
    var mouthAngle: Double = 0
    var audioName: String?
    var audioURL: URL?
    var volume: Double = 1
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
    var editForeground = false
    var editBackground = false
    var selectedPersonID: String?
    var selectedIsMouth = false
    var unlockedMouthID: String?
    var time: TimeInterval = 0
    var note: String?
    var examining = false
    var examineProgress: Double?
    var exportProgress: Double?
    private var players: [String: AVAudioPlayer] = [:]

    private var rotating = false
    private var dragStart: CGPoint?
    private var dragOrigin: (x: Double, y: Double, scale: Double)?
    private var dragSubject: DragSubject?
    private var resizing = false
    private var clickMouthID: String?
    private var lastMouthClick: (id: String, time: Date)?

    private enum DragSubject {
        case foreground
        case background
        case person(String)
        case mouth(String)
    }

    init() {
        let names = [
            ("adam", "Adam"),
            ("ben", "Ben"),
            ("corey", "Corey"),
            ("emily", "Emily"),
            ("abby-r", "Abby R"),
            ("abby-s", "Abby S"),
        ]
        let places: [String: (Double, Double, Double)] = [
            "adam": (51.46, 30.11, 16.43),
            "ben": (51.50, 23.73, 14.31),
            "corey": (52.08, 46.10, 12.85),
            "emily": (50.80, 29.31, 14.16),
            "abby-r": (50.00, 28.80, 17.16),
            "abby-s": (50.62, 30.74, 9.38),
        ]
        people = names.enumerated().compactMap { index, pair in
            let (id, name) = pair
            guard let body = Self.bundleImage("person-\(id)", ext: "png") else { return nil }
            var mouths: [String: CGImage] = [:]
            for shape in Self.shapes {
                if let image = Self.bundleImage("mouth-\(id)-\(shape)", ext: "png") {
                    mouths[shape] = image
                }
            }
            let count = Double(names.count)
            let place = places[id] ?? (50, 34, 14)
            return PersonItem(
                id: id,
                name: name,
                body: body,
                mouths: mouths,
                isOn: true,
                x: (Double(index) + 0.5) / count * 100,
                y: 46,
                scale: 72,
                mouthX: place.0,
                mouthY: place.1,
                mouthScale: place.2
            )
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
        restoreFaces()
        restoreVolumes()
    }

    var background: PictureItem? {
        backgrounds.first { $0.id == backgroundID }
    }

    var foreground: PictureItem? {
        foregrounds.first { $0.id == foregroundID }
    }

    func chooseBackground(_ id: String) {
        backgroundID = id
    }

    func chooseForeground(_ id: String) {
        foregroundID = id
    }

    func setForegroundEditing(_ on: Bool) {
        editForeground = on
        if on { editBackground = false }
    }

    func setBackgroundEditing(_ on: Bool) {
        editBackground = on
        if on { editForeground = false }
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
            setForegroundEditing(true)
        } else {
            backgrounds.append(item)
            backgroundID = item.id
            setBackgroundEditing(true)
        }
        note = "Added \(name)."
    }

    func drag(to point: CGPoint) {
        if dragStart == nil {
            beginDrag(at: point)
        }
        updateDrag(to: point)
    }

    func beginDrag(at point: CGPoint) {
        if editForeground, let foreground {
            let rect = foregroundRect(foreground)
            resizing = handle(for: rect).contains(point)
            dragSubject = .foreground
            dragStart = point
            dragOrigin = (foreground.x, foreground.y, foreground.scale)
            return
        }
        if editBackground, let background {
            resizing = handleRect().contains(point)
            dragSubject = .background
            dragStart = point
            dragOrigin = (background.x, background.y, background.scale)
            return
        }
        for person in people.filter(\.isOn).reversed() {
            let shape = mouthShape(person, time)
            guard let mouth = mouthRect(person, shape: shape) else { continue }
            let corner = handle(for: mouth, size: 16, angle: person.mouthAngle)
            let knob = rotateHandle(for: mouth, angle: person.mouthAngle)
            if unlockedMouthID == person.id && knob.contains(point) {
                selectedPersonID = person.id
                selectedIsMouth = true
                clickMouthID = person.id
                rotating = true
                resizing = false
                dragSubject = .mouth(person.id)
                dragStart = point
                dragOrigin = (person.mouthX, person.mouthY, person.mouthScale)
                return
            }
            if corner.contains(point) || contains(mouth, angle: person.mouthAngle, point: point) {
                selectedPersonID = person.id
                clickMouthID = person.id
                dragStart = point
                if unlockedMouthID == person.id {
                    selectedIsMouth = true
                    resizing = corner.contains(point)
                    rotating = false
                    dragSubject = .mouth(person.id)
                    dragOrigin = (person.mouthX, person.mouthY, person.mouthScale)
                }
                return
            }
        }
        for person in people.filter(\.isOn).reversed() {
            let rect = bodyRect(person)
            let corner = handle(for: rect)
            if corner.contains(point) || rect.contains(point) {
                selectedPersonID = person.id
                selectedIsMouth = false
                resizing = corner.contains(point)
                dragSubject = .person(person.id)
                dragStart = point
                dragOrigin = (person.x, person.y, person.scale)
                return
            }
        }
    }

    func updateDrag(to point: CGPoint) {
        guard let start = dragStart, let origin = dragOrigin, let dragSubject else { return }
        if case .mouth(let id) = dragSubject {
            guard let person = people.first(where: { $0.id == id }) else { return }
            let body = bodyRect(person)
            if rotating, let lips = mouthRect(person, shape: mouthShape(person, time)) {
                let angle = atan2(point.x - lips.midX, lips.midY - point.y) * 180 / .pi
                setMouthAngle(id, angle)
                return
            }
            let dx = Double(point.x - start.x) / Double(max(1, body.width)) * 100
            let dy = Double(point.y - start.y) / Double(max(1, body.height)) * 100
            if resizing {
                setMouth(id, x: origin.x, y: origin.y, scale: min(40, max(4, origin.scale + dx)))
            } else {
                setMouth(id, x: origin.x + dx, y: origin.y + dy, scale: origin.scale)
            }
            return
        }
        let dx = Double((point.x - start.x) / Self.scene.width) * 100
        let dy = Double((point.y - start.y) / Self.scene.height) * 100
        if resizing {
            let limit: ClosedRange<Double>
            switch dragSubject {
            case .foreground: limit = 8...180
            case .background: limit = 40...250
            case .person: limit = 20...140
            case .mouth: return
            }
            setSubject(dragSubject, x: origin.x, y: origin.y, scale: min(limit.upperBound, max(limit.lowerBound, origin.scale + dx)))
        } else {
            setSubject(dragSubject, x: origin.x + dx, y: origin.y + dy, scale: origin.scale)
        }
    }

    func endDrag() {
        dragStart = nil
        dragOrigin = nil
        dragSubject = nil
        resizing = false
        rotating = false
        clickMouthID = nil
    }

    func finishDrag(at point: CGPoint) {
        let moved = dragStart.map { hypot($0.x - point.x, $0.y - point.y) } ?? 999
        let mouthID = clickMouthID
        let turned = rotating || resizing
        endDrag()
        guard !turned, moved < 40, let mouthID else { return }
        let now = Date()
        if let last = lastMouthClick, last.id == mouthID, now.timeIntervalSince(last.time) < 0.45 {
            if unlockedMouthID == mouthID {
                unlockedMouthID = nil
                selectedIsMouth = false
                note = "Mouth locked."
            } else {
                unlockedMouthID = mouthID
                selectedPersonID = mouthID
                selectedIsMouth = true
                note = "Drag the mouth to move it. Drag the circle to turn it. Double-click it again to lock it."
            }
            lastMouthClick = nil
        } else {
            lastMouthClick = (id: mouthID, time: now)
        }
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
        for person in visible {
            let rect = bodyRect(person)
            ctx.draw(person.body, in: placed(rect))
            let shape = mouthShape(person, time)
            if let lips = mouthRect(person, shape: shape) {
                if let mouth = person.mouths[shape] ?? person.mouths["closed"] {
                    drawTurned(mouth, in: lips, angle: person.mouthAngle, context: ctx)
                }
                if !editForeground && !editBackground && unlockedMouthID == person.id {
                    let selected = person.id == selectedPersonID && selectedIsMouth
                    ctx.setStrokeColor(CGColor(srgbRed: 0.77, green: 0.36, blue: 0.15, alpha: 1))
                    ctx.setLineWidth(selected ? 4 : 2)
                    strokeTurned(lips, angle: person.mouthAngle, context: ctx)
                    ctx.setFillColor(CGColor(srgbRed: 0.77, green: 0.36, blue: 0.15, alpha: 1))
                    ctx.fill(placed(handle(for: lips, size: 16, angle: person.mouthAngle)))
                    let knob = rotateHandle(for: lips, angle: person.mouthAngle)
                    let dot = placed(knob)
                    ctx.setFillColor(CGColor(srgbRed: 0.95, green: 0.93, blue: 0.86, alpha: 1))
                    ctx.fillEllipse(in: dot)
                    ctx.setStrokeColor(CGColor(srgbRed: 0.77, green: 0.36, blue: 0.15, alpha: 1))
                    ctx.setLineWidth(3)
                    ctx.strokeEllipse(in: dot)
                }
            }
            if !editForeground && !editBackground && person.id == selectedPersonID && !selectedIsMouth {
                let drawn = placed(rect)
                ctx.setStrokeColor(CGColor(srgbRed: 0.77, green: 0.36, blue: 0.15, alpha: 1))
                ctx.setLineWidth(4)
                ctx.stroke(drawn)
                ctx.setFillColor(CGColor(srgbRed: 0.77, green: 0.36, blue: 0.15, alpha: 1))
                ctx.fill(placed(handle(for: rect)))
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
            if editForeground {
                ctx.setStrokeColor(CGColor(srgbRed: 0.77, green: 0.36, blue: 0.15, alpha: 1))
                ctx.setLineWidth(4)
                ctx.stroke(drawn)
            }
        }
        ctx.restoreGState()
        if editBackground {
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
            let player = try AVAudioPlayer(contentsOf: copy)
            player.prepareToPlay()
            if let index = people.firstIndex(where: { $0.id == personID }) {
                people[index].audioURL = copy
                people[index].audioName = url.deletingPathExtension().lastPathComponent
                people[index].levels = []
            }
            players[personID] = player
            note = "Audio loaded. Press Examine audio and sync mouths."
        } catch {
            note = "Could not read that audio. Use a wav, mp3, or m4a file."
        }
    }

    func examineAndSync() {
        let jobs = people.compactMap { person -> (String, URL)? in
            guard person.isOn, let url = person.audioURL else { return nil }
            return (person.id, url)
        }
        guard !jobs.isEmpty else {
            note = "Load audio for a person first."
            return
        }
        examining = true
        examineProgress = 0
        note = "Examining audio…"
        DispatchQueue.global(qos: .userInitiated).async {
            var results: [(String, [Float])] = []
            for (offset, job) in jobs.enumerated() {
                let levels = (try? Self.levels(in: job.1)) ?? []
                results.append((job.0, levels))
                let progress = Double(offset + 1) / Double(jobs.count)
                DispatchQueue.main.async { self.examineProgress = progress }
            }
            DispatchQueue.main.async {
                for (id, levels) in results {
                    if let index = self.people.firstIndex(where: { $0.id == id }) {
                        self.people[index].levels = levels
                    }
                }
                self.examining = false
                self.examineProgress = nil
                let synced = results.filter { !$0.1.isEmpty }.count
                self.note = synced == 0
                    ? "Could not read the audio."
                    : "Synced mouths for \(synced) \(synced == 1 ? "person" : "people")."
            }
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
            player.volume = Float(person.volume)
            player.play()
        }
    }

    func setVolume(_ id: String, _ volume: Double) {
        let volume = min(1, max(0, volume))
        guard let index = people.firstIndex(where: { $0.id == id }) else { return }
        people[index].volume = volume
        players[id]?.volume = Float(volume)
        var saved = UserDefaults.standard.dictionary(forKey: "person-volumes") ?? [:]
        saved[id] = volume
        UserDefaults.standard.set(saved, forKey: "person-volumes")
    }

    func stopAudio() {
        for player in players.values {
            player.pause()
        }
    }

    private func restoreVolumes() {
        guard let saved = UserDefaults.standard.dictionary(forKey: "person-volumes") else { return }
        for (id, value) in saved {
            let volume = (value as? NSNumber)?.doubleValue ?? 1
            guard let index = people.firstIndex(where: { $0.id == id }) else { continue }
            people[index].volume = min(1, max(0, volume))
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
        DispatchQueue.main.async {
            self.note = "Writing the movie…"
            self.exportProgress = 0.01
        }
        let tracks = people.filter(\.isOn).compactMap { person -> (URL, Float)? in
            guard let audioURL = person.audioURL else { return nil }
            return (audioURL, Float(person.volume))
        }
        let pumps = tracks.compactMap { AudioPump(url: $0.0, volume: $0.1) }
        let levelDuration = people.filter(\.isOn).map { Double($0.levels.count) * 0.08 }.max() ?? 0
        let soundDuration = pumps.map(\.duration).max() ?? 0
        let duration = max(soundDuration, levelDuration) > 0.2 ? max(soundDuration, levelDuration) : 4
        let mixURL = try writeMix(pumps, duration: duration)
        defer { if let mixURL { try? FileManager.default.removeItem(at: mixURL) } }
        guard let mixURL else {
            try writeVideo(to: url, duration: duration, progressStart: 0.02, progressEnd: 1)
            return
        }
        let pictureURL = FileManager.default.temporaryDirectory.appendingPathComponent("podcast-picture-\(UUID().uuidString).mp4")
        let soundURL = FileManager.default.temporaryDirectory.appendingPathComponent("podcast-sound-\(UUID().uuidString).m4a")
        defer {
            try? FileManager.default.removeItem(at: pictureURL)
            try? FileManager.default.removeItem(at: soundURL)
        }
        try writeVideo(to: pictureURL, duration: duration, progressStart: 0.15, progressEnd: 0.8)
        try writeCompressedAudio(from: mixURL, to: soundURL)
        try join(video: pictureURL, audio: soundURL, to: url)
    }

    private func writeVideo(to url: URL, duration: Double, progressStart: Double, progressEnd: Double) throws {
        DispatchQueue.main.async { self.note = "Writing the picture…" }
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
        guard writer.startWriting() else { throw writer.error ?? ExportFailure("Could not start the picture.") }
        writer.startSession(atSourceTime: .zero)
        let fps = 12
        let frames = max(1, Int(duration * Double(fps)))
        var stalls = 0
        for index in 0..<frames {
            while !input.isReadyForMoreMediaData {
                stalls += 1
                if stalls > 15000 {
                    writer.cancelWriting()
                    throw writer.error ?? ExportFailure("The picture encoder stopped.")
                }
                Thread.sleep(forTimeInterval: 0.002)
            }
            stalls = 0
            let sample = Double(index) / Double(fps)
            if let image = frame(at: sample), let buffer = pixelBuffer(from: image) {
                let time = CMTime(value: CMTimeValue(index), timescale: CMTimeScale(fps))
                if !adaptor.append(buffer, withPresentationTime: time) {
                    throw writer.error ?? ExportFailure("Could not add a picture frame.")
                }
            }
            if index % 3 == 0 {
                let progress = progressStart + Double(index) / Double(frames) * (progressEnd - progressStart)
                DispatchQueue.main.async { self.exportProgress = progress }
            }
        }
        input.markAsFinished()
        try finish(writer)
    }

    private func writeCompressedAudio(from source: URL, to url: URL) throws {
        DispatchQueue.main.async {
            self.note = "Adding the sound…"
            self.exportProgress = 0.82
        }
        if FileManager.default.fileExists(atPath: url.path) {
            try FileManager.default.removeItem(at: url)
        }
        let sound = try openSound(source)
        let writer = try AVAssetWriter(outputURL: url, fileType: .m4a)
        var layout = AudioChannelLayout()
        layout.mChannelLayoutTag = kAudioChannelLayoutTag_Stereo
        let layoutData = Data(bytes: &layout, count: MemoryLayout<AudioChannelLayout>.size)
        let input = AVAssetWriterInput(mediaType: .audio, outputSettings: [
            AVFormatIDKey: kAudioFormatMPEG4AAC,
            AVSampleRateKey: 44_100,
            AVNumberOfChannelsKey: 2,
            AVEncoderBitRateKey: 160_000,
            AVChannelLayoutKey: layoutData,
        ])
        input.expectsMediaDataInRealTime = false
        writer.add(input)
        guard writer.startWriting() else { throw writer.error ?? ExportFailure("Could not start the sound file.") }
        writer.startSession(atSourceTime: .zero)
        var stalls = 0
        while sound.reader.status == .reading {
            if !input.isReadyForMoreMediaData {
                stalls += 1
                if stalls > 15000 {
                    writer.cancelWriting()
                    throw writer.error ?? ExportFailure("The sound encoder stopped.")
                }
                Thread.sleep(forTimeInterval: 0.002)
                continue
            }
            stalls = 0
            guard let sample = sound.output.copyNextSampleBuffer() else { break }
            if !input.append(sample) {
                throw writer.error ?? ExportFailure("Could not add the sound.")
            }
        }
        if sound.reader.status == .failed {
            throw sound.reader.error ?? ExportFailure("Could not read the mixed sound.")
        }
        input.markAsFinished()
        try finish(writer)
    }

    private func join(video videoURL: URL, audio audioURL: URL, to url: URL) throws {
        DispatchQueue.main.async {
            self.note = "Finishing the movie…"
            self.exportProgress = 0.9
        }
        let picture = AVURLAsset(url: videoURL)
        let sound = AVURLAsset(url: audioURL)
        waitUntilLoaded(picture)
        waitUntilLoaded(sound)
        guard let pictureTrack = picture.tracks(withMediaType: .video).first,
              let soundTrack = sound.tracks(withMediaType: .audio).first else {
            throw ExportFailure("The picture or the sound could not be opened.")
        }
        let composition = AVMutableComposition()
        guard let videoTrack = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid),
              let audioTrack = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) else {
            throw ExportFailure("Could not build the movie.")
        }
        let pictureDuration = picture.duration
        let soundDuration = CMTimeMinimum(sound.duration, pictureDuration)
        try videoTrack.insertTimeRange(CMTimeRange(start: .zero, duration: pictureDuration), of: pictureTrack, at: .zero)
        try audioTrack.insertTimeRange(CMTimeRange(start: .zero, duration: soundDuration), of: soundTrack, at: .zero)
        if FileManager.default.fileExists(atPath: url.path) {
            try FileManager.default.removeItem(at: url)
        }
        do {
            try export(composition, to: url, preset: AVAssetExportPresetPassthrough)
        } catch {
            try? FileManager.default.removeItem(at: url)
            try export(composition, to: url, preset: AVAssetExportPreset1280x720)
        }
    }

    private func export(_ composition: AVMutableComposition, to url: URL, preset: String) throws {
        guard let session = AVAssetExportSession(asset: composition, presetName: preset) else {
            throw ExportFailure("Could not finish the movie.")
        }
        session.outputURL = url
        session.outputFileType = session.supportedFileTypes.contains(.mp4) ? .mp4 : session.supportedFileTypes.first
        guard session.outputFileType != nil else { throw ExportFailure("Could not choose a movie type.") }
        let wait = DispatchSemaphore(value: 0)
        session.exportAsynchronously { wait.signal() }
        while wait.wait(timeout: .now() + 0.25) == .timedOut {
            let progress = 0.9 + Double(session.progress) * 0.1
            DispatchQueue.main.async { self.exportProgress = progress }
        }
        if session.status != .completed {
            throw session.error ?? ExportFailure("Could not finish the movie.")
        }
    }

    private func finish(_ writer: AVAssetWriter) throws {
        let wait = DispatchSemaphore(value: 0)
        writer.finishWriting { wait.signal() }
        if wait.wait(timeout: .now() + 180) == .timedOut {
            writer.cancelWriting()
            throw ExportFailure("Saving the movie took too long.")
        }
        if writer.status != .completed {
            throw writer.error ?? ExportFailure("The movie file was not finished.")
        }
    }

    private func waitUntilLoaded(_ asset: AVURLAsset) {
        let wait = DispatchSemaphore(value: 0)
        asset.loadValuesAsynchronously(forKeys: ["tracks", "duration"]) { wait.signal() }
        wait.wait()
    }

    private func writeMix(_ pumps: [AudioPump], duration: Double) throws -> URL? {
        guard !pumps.isEmpty, duration > 0.05 else { return nil }
        DispatchQueue.main.async {
            self.note = "Mixing the sound…"
            self.exportProgress = 0.01
        }
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("podcast-mix-\(UUID().uuidString).caf")
        let format = AudioPump.outputFormat
        let file = try AVAudioFile(forWriting: url, settings: format.settings, commonFormat: format.commonFormat, interleaved: false)
        let total = max(1, AVAudioFrameCount(duration * format.sampleRate))
        var written: AVAudioFrameCount = 0
        while written < total {
            let count = min(AVAudioFrameCount(16_384), total - written)
            try file.write(from: mixChunk(pumps, frames: count))
            written += count
            let progress = min(0.15, Double(written) / Double(total) * 0.15)
            DispatchQueue.main.async { self.exportProgress = progress }
        }
        return url
    }

    private func openSound(_ url: URL) throws -> (reader: AVAssetReader, output: AVAssetReaderTrackOutput) {
        let asset = AVURLAsset(url: url)
        let reader = try AVAssetReader(asset: asset)
        guard let track = asset.tracks(withMediaType: .audio).first else {
            throw ExportFailure("The mixed sound had no audio.")
        }
        let output = AVAssetReaderTrackOutput(track: track, outputSettings: [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsBigEndianKey: false,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsNonInterleaved: false,
            AVSampleRateKey: 44_100,
            AVNumberOfChannelsKey: 2,
        ])
        output.alwaysCopiesSampleData = true
        reader.add(output)
        guard reader.startReading() else {
            throw reader.error ?? ExportFailure("Could not read the mixed sound.")
        }
        return (reader, output)
    }

    private func mixChunk(_ pumps: [AudioPump], frames: AVAudioFrameCount) -> AVAudioPCMBuffer {
        let format = AudioPump.outputFormat
        guard let mix = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames) else {
            return AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 1)!
        }
        mix.frameLength = frames
        let count = Int(frames)
        for channel in 0..<2 {
            guard let dest = mix.floatChannelData?[channel] else { continue }
            for index in 0..<count { dest[index] = 0 }
        }
        for pump in pumps {
            guard let part = pump.pull(frames), let left = part.floatChannelData?[0] else { continue }
            let right = part.floatChannelData?[min(1, Int(part.format.channelCount) - 1)] ?? left
            let partCount = min(count, Int(part.frameLength))
            if let destL = mix.floatChannelData?[0], let destR = mix.floatChannelData?[1] {
                for index in 0..<partCount {
                    destL[index] += left[index] * pump.volume
                    destR[index] += right[index] * pump.volume
                }
            }
        }
        for channel in 0..<2 {
            guard let dest = mix.floatChannelData?[channel] else { continue }
            for index in 0..<count {
                dest[index] = max(-1, min(1, dest[index]))
            }
        }
        return mix
    }

    private final class AudioPump {
    static let outputFormat: AVAudioFormat = AVAudioFormat(
        commonFormat: .pcmFormatFloat32,
        sampleRate: 44100,
        channels: 2,
        interleaved: false
    )!

    let volume: Float
    let duration: Double
    private let file: AVAudioFile
    private let converter: AVAudioConverter
    private var ended = false

    init?(url: URL, volume: Float) {
        guard let file = try? AVAudioFile(forReading: url),
              let converter = AVAudioConverter(from: file.processingFormat, to: Self.outputFormat) else { return nil }
        self.file = file
        self.converter = converter
        self.volume = volume
        self.duration = Double(file.length) / file.processingFormat.sampleRate
    }

    func pull(_ frames: AVAudioFrameCount) -> AVAudioPCMBuffer? {
        if ended { return nil }
        guard let output = AVAudioPCMBuffer(pcmFormat: Self.outputFormat, frameCapacity: frames) else { return nil }
        var error: NSError?
        let sourceFile = self.file
        let status = converter.convert(to: output, error: &error) { _, inputStatus in
            guard let source = AVAudioPCMBuffer(pcmFormat: sourceFile.processingFormat, frameCapacity: 2048) else {
                inputStatus.pointee = .noDataNow
                return nil
            }
            do {
                try sourceFile.read(into: source, frameCount: 2048)
            } catch {
                inputStatus.pointee = .endOfStream
                return nil
            }
            if source.frameLength == 0 {
                inputStatus.pointee = .endOfStream
                return nil
            }
            inputStatus.pointee = .haveData
            return source
        }
        if error != nil || output.frameLength == 0 {
            ended = true
            return output.frameLength > 0 ? output : nil
        }
        if status == .endOfStream { ended = true }
        return output
    }
}

private struct ExportFailure: LocalizedError {
    var errorDescription: String?
    init(_ message: String) { errorDescription = message }
}

    private func setSubject(_ subject: DragSubject, x: Double, y: Double, scale: Double) {
        switch subject {
        case .foreground:
            guard let index = foregrounds.firstIndex(where: { $0.id == foregroundID }) else { return }
            foregrounds[index].x = x
            foregrounds[index].y = y
            foregrounds[index].scale = scale
        case .background:
            guard let index = backgrounds.firstIndex(where: { $0.id == backgroundID }) else { return }
            backgrounds[index].x = x
            backgrounds[index].y = y
            backgrounds[index].scale = scale
        case .person(let id):
            guard let index = people.firstIndex(where: { $0.id == id }) else { return }
            people[index].x = x
            people[index].y = y
            people[index].scale = scale
        case .mouth:
            return
        }
    }

    private func setMouth(_ id: String, x: Double, y: Double, scale: Double) {
        guard let index = people.firstIndex(where: { $0.id == id }) else { return }
        var next = people[index]
        next.mouthScale = min(80, max(4, scale))
        next.mouthX = x
        next.mouthY = y
        let shape = mouthShape(next, time)
        guard let mouth = next.mouths[shape] ?? next.mouths["closed"] else { return }
        let body = bodyRect(next)
        let mw = body.width * CGFloat(next.mouthScale / 100)
        let mh = mw * CGFloat(mouth.height) / CGFloat(max(1, mouth.width))
        let halfX = Double(mw / 2 / max(body.width, 1)) * 100
        let halfY = Double(mh / 2 / max(body.height, 1)) * 100
        next.mouthX = halfX < 50 ? min(100 - halfX, max(halfX, next.mouthX)) : 50
        next.mouthY = halfY < 50 ? min(100 - halfY, max(halfY, next.mouthY)) : 50
        people[index].mouthX = next.mouthX
        people[index].mouthY = next.mouthY
        people[index].mouthScale = next.mouthScale
    }

    func setMouthAngle(_ id: String, _ angle: Double) {
        guard let index = people.firstIndex(where: { $0.id == id }) else { return }
        var degrees = angle.truncatingRemainder(dividingBy: 360)
        if degrees > 180 { degrees -= 360 }
        if degrees < -180 { degrees += 360 }
        people[index].mouthAngle = degrees
    }

    func saveFaces() {
        let faces = people.map {
            SavedFace(id: $0.id, x: $0.x, y: $0.y, scale: $0.scale, mouthX: $0.mouthX, mouthY: $0.mouthY, mouthScale: $0.mouthScale, mouthAngle: $0.mouthAngle)
        }
        guard let data = try? JSONEncoder().encode(faces) else { return }
        UserDefaults.standard.set(data, forKey: "saved-faces-v6")
        note = "Face positions saved. The next project will start lined up."
    }

    private func restoreFaces() {
        let keys = ["saved-faces-v6", "saved-faces-v5", "saved-faces-v4", "saved-faces-v3", "saved-faces-v2"]
        var data: Data?
        var keyUsed = ""
        for key in keys {
            if let found = UserDefaults.standard.data(forKey: key) {
                data = found
                keyUsed = key
                break
            }
        }
        guard let data, let faces = try? JSONDecoder().decode([SavedFace].self, from: data) else { return }
        for face in faces {
            guard let index = people.firstIndex(where: { $0.id == face.id }) else { continue }
            people[index].x = face.x
            people[index].y = face.y
            people[index].scale = face.scale
            if keyUsed == "saved-faces-v6" {
                people[index].mouthX = face.mouthX
                people[index].mouthY = face.mouthY
                people[index].mouthScale = face.mouthScale
                people[index].mouthAngle = face.mouthAngle
            }
        }
    }

    private func mouthRect(_ person: PersonItem, shape: String) -> CGRect? {
        guard person.mouths[shape] ?? person.mouths["closed"] != nil else { return nil }
        let mouth = (person.mouths[shape] ?? person.mouths["closed"])!
        let rect = bodyRect(person)
        let mw = rect.width * CGFloat(person.mouthScale / 100)
        let mh = mw * CGFloat(mouth.height) / CGFloat(max(1, mouth.width))
        return CGRect(
            x: rect.minX + rect.width * CGFloat(person.mouthX / 100) - mw / 2,
            y: rect.minY + rect.height * CGFloat(person.mouthY / 100) - mh / 2,
            width: mw,
            height: mh
        )
    }

    private func bodyRect(_ person: PersonItem) -> CGRect {
        let canvas = Self.scene
        let bodyH = canvas.height * CGFloat(person.scale / 100)
        let bodyW = bodyH * CGFloat(person.body.width) / CGFloat(max(1, person.body.height))
        let cx = CGFloat(person.x / 100) * canvas.width
        let cy = CGFloat(person.y / 100) * canvas.height
        return CGRect(x: cx - bodyW / 2, y: cy - bodyH / 2, width: bodyW, height: bodyH)
    }

    private func foregroundRect(_ item: PictureItem) -> CGRect {
        let canvas = Self.scene
        let height = canvas.height * CGFloat(item.scale / 100)
        let width = height * CGFloat(item.image.width) / CGFloat(max(1, item.image.height))
        return CGRect(
            x: CGFloat(item.x / 100) * canvas.width - width / 2,
            y: CGFloat(item.y / 100) * canvas.height - height / 2,
            width: width,
            height: height
        )
    }

    private func handle(for rect: CGRect, size: CGFloat = 36, angle: Double = 0) -> CGRect {
        let center = turned(CGPoint(x: rect.width / 2 - size / 2, y: rect.height / 2 - size / 2), around: rect, angle: angle)
        return CGRect(x: center.x - size / 2, y: center.y - size / 2, width: size, height: size)
    }

    private func rotateHandle(for rect: CGRect, angle: Double) -> CGRect {
        let center = turned(CGPoint(x: 0, y: -(rect.height / 2 + 22)), around: rect, angle: angle)
        return CGRect(x: center.x - 9, y: center.y - 9, width: 18, height: 18)
    }

    private func turned(_ local: CGPoint, around rect: CGRect, angle: Double) -> CGPoint {
        let rad = angle * .pi / 180
        let c = cos(rad)
        let s = sin(rad)
        return CGPoint(
            x: rect.midX + local.x * c - local.y * s,
            y: rect.midY + local.x * s + local.y * c
        )
    }

    private func contains(_ rect: CGRect, angle: Double, point: CGPoint) -> Bool {
        let rad = -angle * .pi / 180
        let c = cos(rad)
        let s = sin(rad)
        let dx = point.x - rect.midX
        let dy = point.y - rect.midY
        let x = dx * c + dy * s
        let y = -dx * s + dy * c
        return abs(x) <= rect.width / 2 && abs(y) <= rect.height / 2
    }

    private func drawTurned(_ image: CGImage, in rect: CGRect, angle: Double, context ctx: CGContext) {
        let box = placed(rect)
        ctx.saveGState()
        ctx.translateBy(x: box.midX, y: box.midY)
        ctx.rotate(by: -CGFloat(angle) * .pi / 180)
        ctx.draw(image, in: CGRect(x: -box.width / 2, y: -box.height / 2, width: box.width, height: box.height))
        ctx.restoreGState()
    }

    private func strokeTurned(_ rect: CGRect, angle: Double, context ctx: CGContext) {
        let corners = [
            turned(CGPoint(x: -rect.width / 2, y: -rect.height / 2), around: rect, angle: angle),
            turned(CGPoint(x: rect.width / 2, y: -rect.height / 2), around: rect, angle: angle),
            turned(CGPoint(x: rect.width / 2, y: rect.height / 2), around: rect, angle: angle),
            turned(CGPoint(x: -rect.width / 2, y: rect.height / 2), around: rect, angle: angle),
        ]
        ctx.beginPath()
        let first = CGPoint(x: corners[0].x, y: Self.scene.height - corners[0].y)
        ctx.move(to: first)
        for corner in corners.dropFirst() {
            ctx.addLine(to: CGPoint(x: corner.x, y: Self.scene.height - corner.y))
        }
        ctx.closePath()
        ctx.strokePath()
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
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
        return CGImageSourceCreateImageAtIndex(source, 0, nil)
    }
}

struct SavedFace: Codable {
    var id: String
    var x: Double
    var y: Double
    var scale: Double
    var mouthX: Double
    var mouthY: Double
    var mouthScale: Double
    var mouthAngle: Double

    enum CodingKeys: String, CodingKey {
        case id, x, y, scale, mouthX, mouthY, mouthScale, mouthAngle
    }

    init(id: String, x: Double, y: Double, scale: Double, mouthX: Double, mouthY: Double, mouthScale: Double, mouthAngle: Double) {
        self.id = id
        self.x = x
        self.y = y
        self.scale = scale
        self.mouthX = mouthX
        self.mouthY = mouthY
        self.mouthScale = mouthScale
        self.mouthAngle = mouthAngle
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(String.self, forKey: .id)
        x = try values.decode(Double.self, forKey: .x)
        y = try values.decode(Double.self, forKey: .y)
        scale = try values.decode(Double.self, forKey: .scale)
        mouthX = try values.decode(Double.self, forKey: .mouthX)
        mouthY = try values.decode(Double.self, forKey: .mouthY)
        mouthScale = try values.decode(Double.self, forKey: .mouthScale)
        mouthAngle = try values.decodeIfPresent(Double.self, forKey: .mouthAngle) ?? 0
    }

    func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(id, forKey: .id)
        try values.encode(x, forKey: .x)
        try values.encode(y, forKey: .y)
        try values.encode(scale, forKey: .scale)
        try values.encode(mouthX, forKey: .mouthX)
        try values.encode(mouthY, forKey: .mouthY)
        try values.encode(mouthScale, forKey: .mouthScale)
        try values.encode(mouthAngle, forKey: .mouthAngle)
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
