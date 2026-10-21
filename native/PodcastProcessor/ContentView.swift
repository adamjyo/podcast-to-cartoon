import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @State private var model = EditorModel()
    @State private var playing = false
    @State private var showImage = false
    @State private var imageLayer: EditLayer = .background
    @State private var audioPerson: String?
    @State private var showAudio = false
    @State private var pngFile: PNGFile?
    @State private var movieFile: MovieFile?
    @State private var showPNG = false
    @State private var showMovie = false
    @State private var busy = false

    var body: some View {
        GeometryReader { geo in
            HStack(spacing: 0) {
                sceneColumn
                    .frame(width: geo.size.width * 0.75)
                optionsColumn
                    .frame(width: geo.size.width * 0.25)
            }
        }
        .background(Color.paper)
        .preferredColorScheme(.light)
        .tint(Color.ink)
        .fileImporter(
            isPresented: $showImage,
            allowedContentTypes: [.png, .jpeg, .heic, .gif, .tiff, .bmp, .webP, .image],
            allowsMultipleSelection: false
        ) { result in
            let layer = imageLayer
            switch result {
            case .failure:
                model.note = "Could not open the picture picker."
            case .success(let urls):
                guard let url = urls.first else {
                    model.note = "No picture was selected."
                    return
                }
                let allowed = url.startAccessingSecurityScopedResource()
                defer { if allowed { url.stopAccessingSecurityScopedResource() } }
                do {
                    let data = try Data(contentsOf: url)
                    let name = url.deletingPathExtension().lastPathComponent
                    model.addImage(data: data, name: name.isEmpty ? "New" : name, layer: layer)
                } catch {
                    model.note = "Could not read that picture."
                }
            }
        }
        .fileImporter(isPresented: $showAudio, allowedContentTypes: [.wav, .mp3, .mpeg4Audio, .aiff, .audio]) { result in
            defer { audioPerson = nil }
            guard let personID = audioPerson else { return }
            if case .success(let url) = result {
                model.loadAudio(from: url, personID: personID)
            }
        }
        .fileExporter(isPresented: $showPNG, document: pngFile, contentType: .png, defaultFilename: "scene.png") { _ in }
        .fileExporter(isPresented: $showMovie, document: movieFile, contentType: .mpeg4Movie, defaultFilename: "scene.mp4") { _ in }
        .task(id: playing) {
            guard playing else {
                model.stopAudio()
                return
            }
            model.startAudio()
            let start = Date()
            while !Task.isCancelled && playing {
                let elapsed = Date().timeIntervalSince(start)
                model.time = elapsed
                if model.audioFinished(elapsed) {
                    playing = false
                    break
                }
                try? await Task.sleep(for: .milliseconds(80))
            }
        }
    }

    private var sceneColumn: some View {
        GeometryReader { column in
            VStack(spacing: 12) {
                scene
                    .frame(height: max(220, column.size.height * 0.62))
                    .padding(.horizontal, 12)
                    .padding(.top, 12)
                ScrollView {
                    layerBar(
                        title: "Foreground",
                        active: model.editForeground,
                        selection: model.foregroundID,
                        options: [("none", "None")] + model.foregrounds.map { ($0.id, $0.name) },
                        choose: { model.chooseForeground($0) },
                        add: {
                            imageLayer = .foreground
                            showImage = true
                        },
                        toggle: { model.setForegroundEditing($0) }
                    )
                    layerBar(
                        title: "Background",
                        active: model.editBackground,
                        selection: model.backgroundID,
                        options: model.backgrounds.map { ($0.id, $0.name) },
                        choose: { model.chooseBackground($0) },
                        add: {
                            imageLayer = .background
                            showImage = true
                        },
                        toggle: { model.setBackgroundEditing($0) }
                    )
                    if let note = model.note {
                        Text(note)
                            .font(.subheadline)
                            .foregroundStyle(Color.sienna)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.bottom, 12)
            }
        }
        .padding(.horizontal, 12)
    }

    private var scene: some View {
        GeometryReader { geo in
            let fit = fitted(geo.size)
            ZStack {
                Color.ink
                if let frame = model.frame(at: model.time) {
                    Image(decorative: frame, scale: 1)
                        .resizable()
                        .interpolation(.high)
                        .frame(width: fit.width, height: fit.height)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 18))
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        let local = CGPoint(
                            x: value.location.x - (geo.size.width - fit.width) / 2,
                            y: value.location.y - (geo.size.height - fit.height) / 2
                        )
                        let scenePoint = CGPoint(
                            x: local.x / fit.width * EditorModel.scene.width,
                            y: local.y / fit.height * EditorModel.scene.height
                        )
                        model.drag(to: scenePoint)
                    }
                    .onEnded { value in
                        let local = CGPoint(
                            x: value.location.x - (geo.size.width - fit.width) / 2,
                            y: value.location.y - (geo.size.height - fit.height) / 2
                        )
                        let scenePoint = CGPoint(
                            x: local.x / fit.width * EditorModel.scene.width,
                            y: local.y / fit.height * EditorModel.scene.height
                        )
                        model.finishDrag(at: scenePoint)
                    }
            )
        }
    }

    private var optionsColumn: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Options")
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(Color.ink)
                Text(model.editForeground
                     ? "Foreground is on. Only that layer can be moved."
                     : model.editBackground
                     ? "Background is on. Drag the picture. Drag the orange corner to resize."
                     : "Both layers are off. Double-click a mouth to move it inside that person. Double-click it again to lock it.")
                    .font(.subheadline)
                    .foregroundStyle(Color.ink.opacity(0.75))
                ForEach(model.people) { person in
                    VStack(alignment: .leading, spacing: 6) {
                        Toggle(person.name, isOn: Binding(
                            get: { person.isOn },
                            set: { value in
                                if let index = model.people.firstIndex(where: { $0.id == person.id }) {
                                    model.people[index].isOn = value
                                }
                            }
                        ))
                        .tint(Color.sienna)
                        .foregroundStyle(Color.ink)
                        Button("Load audio") {
                            audioPerson = person.id
                            showAudio = true
                        }
                        .buttonStyle(.bordered)
                        .tint(Color.ink)
                        .foregroundStyle(Color.ink)
                        if let audioName = person.audioName {
                            Text(audioName)
                                .font(.footnote)
                                .foregroundStyle(Color.ink)
                        }
                    }
                }
                Button(model.examining ? "Examining…" : "Examine audio and sync mouths") {
                    model.examineAndSync()
                }
                .buttonStyle(.borderedProminent)
                .tint(Color.ink)
                .disabled(model.examining)
                if let progress = model.examineProgress {
                    ProgressView(value: progress)
                        .tint(Color.ink)
                }
                HStack {
                    Button(playing ? "Pause" : "Play") {
                        if !playing && !model.hasAudio {
                            model.note = model.people.contains { $0.audioURL != nil }
                                ? "Press Examine audio and sync mouths first."
                                : "Load audio for a person first."
                            return
                        }
                        playing.toggle()
                    }
                        .buttonStyle(.borderedProminent)
                        .tint(Color.ink)
                    Button("Export picture") { exportPNG() }
                        .buttonStyle(.bordered)
                        .tint(Color.ink)
                        .foregroundStyle(Color.ink)
                    Button(busy ? "Exporting…" : "Export movie") { exportMovie() }
                        .buttonStyle(.borderedProminent)
                        .tint(Color.sienna)
                        .disabled(busy)
                }
                if let note = model.note {
                    Text(note)
                        .font(.subheadline)
                        .foregroundStyle(Color.sienna)
                }
                Text("Mac and iPad use this same app. Turn someone off to leave them out of the picture.")
                    .font(.footnote)
                    .foregroundStyle(Color.ink.opacity(0.7))
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Color.paper)
        .overlay(alignment: .leading) { Rectangle().fill(Color.ink.opacity(0.12)).frame(width: 1) }
    }

    private func layerBar(
        title: String,
        active: Bool,
        selection: String,
        options: [(String, String)],
        choose: @escaping (String) -> Void,
        add: @escaping () -> Void,
        toggle: @escaping (Bool) -> Void
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Toggle(title, isOn: Binding(get: { active }, set: toggle))
                    .toggleStyle(.switch)
                    .tint(Color.sienna)
                    .foregroundStyle(Color.ink)
                Picker(title, selection: Binding(get: { selection }, set: choose)) {
                    ForEach(options, id: \.0) { option in
                        Text(option.1).tag(option.0)
                    }
                }
                .pickerStyle(.menu)
                .tint(Color.ink)
                .foregroundStyle(Color.ink)
                .frame(maxWidth: .infinity, alignment: .leading)
                Button("Add new", action: add)
                    .buttonStyle(.bordered)
                    .tint(Color.ink)
                    .foregroundStyle(Color.ink)
            }
            Text(active ? "\(title) is on. Only this can be moved." : "Off.")
                .font(.footnote)
                .foregroundStyle(Color.ink.opacity(0.7))
        }
        .padding(12)
        .background(active ? Color.cream : Color.paper, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(active ? Color.sienna : Color.ink.opacity(0.12), lineWidth: active ? 2 : 1))
    }

    private func fitted(_ size: CGSize) -> CGSize {
        let aspect = EditorModel.scene.width / EditorModel.scene.height
        var width = size.width
        var height = width / aspect
        if height > size.height {
            height = size.height
            width = height * aspect
        }
        return CGSize(width: max(1, width), height: max(1, height))
    }

    private func exportPNG() {
        guard let data = model.pngData() else {
            model.note = "Could not draw the scene."
            return
        }
        pngFile = PNGFile(data: data)
        showPNG = true
    }

    private func exportMovie() {
        busy = true
        let model = model
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("scene-\(UUID().uuidString).mp4")
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                try model.writeMovie(to: url)
                DispatchQueue.main.async {
                    movieFile = MovieFile(url: url)
                    showMovie = true
                    busy = false
                }
            } catch {
                DispatchQueue.main.async {
                    model.note = error.localizedDescription
                    busy = false
                }
            }
        }
    }
}

private extension Color {
    static let paper = Color(red: 0.953, green: 0.925, blue: 0.875)
    static let ink = Color(red: 0.110, green: 0.141, blue: 0.125)
    static let sienna = Color(red: 0.769, green: 0.361, blue: 0.149)
    static let cream = Color(red: 1, green: 0.980, blue: 0.953)
}
