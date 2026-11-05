import AVFoundation
import CoreImage
import ReplayKit
import UniformTypeIdentifiers

/**
 Espejo de pantalla: iOS entrega a esta extensión cada cuadro de la pantalla y el sonido de las apps.
 Se codifican en H.264/AAC en trozos de 1 segundo (HLS) y se sirven por Wi-Fi para que el Chromecast
 los reproduzca. Siempre sale en horizontal 1280×720: si el iPhone está vertical, se centra con bordes negros.
 */
final class SampleHandler: RPBroadcastSampleHandler, AVAssetWriterDelegate {
    private static let width = 1280
    private static let height = 720

    private let server = HLSServer()
    private var writer: AVAssetWriter?
    private var videoInput: AVAssetWriterInput?
    private var audioInput: AVAssetWriterInput?
    private var adaptor: AVAssetWriterInputPixelBufferAdaptor?
    private let ci = CIContext(options: [.cacheIntermediates: false])
    private var started = false
    private var lastVideo = CMTime.invalid
    private let queue = DispatchQueue(label: "mirror")

    /// Último cuadro enviado: se repite si la pantalla no cambia, para que la TV no se quede sin video y corte.
    private var lastFrame: CVPixelBuffer?
    private var timer: DispatchSourceTimer?

    override func broadcastStarted(withSetupInfo setupInfo: [String: NSObject]?) {
        server.start()
        setupWriter()
        let t = DispatchSource.makeTimerSource(queue: queue)
        t.schedule(deadline: .now() + 0.1, repeating: 0.1)
        t.setEventHandler { [weak self] in self?.repeatFrame() }
        t.resume()
        timer = t
    }

    private func repeatFrame() {
        guard started, let frame = lastFrame, let input = videoInput, let adaptor = adaptor,
              input.isReadyForMoreMediaData else { return }
        let now = CMClockGetTime(CMClockGetHostTimeClock())
        guard lastVideo.isValid, CMTimeGetSeconds(CMTimeSubtract(now, lastVideo)) > 0.09 else { return }
        if adaptor.append(frame, withPresentationTime: now) { lastVideo = now }
    }

    override func broadcastFinished() {
        timer?.cancel()
        timer = nil
        server.stop()
        videoInput?.markAsFinished()
        audioInput?.markAsFinished()
        writer?.cancelWriting()
    }

    private func setupWriter() {
        let w = AVAssetWriter(contentType: UTType(AVFileType.mp4.rawValue)!)
        w.outputFileTypeProfile = .mpeg4AppleHLS
        // Trozos de medio segundo: menos retraso en la TV.
        w.preferredOutputSegmentInterval = CMTime(value: 1, timescale: 2)
        w.delegate = self

        let video = AVAssetWriterInput(mediaType: .video, outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: Self.width,
            AVVideoHeightKey: Self.height,
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: 3_000_000,
                AVVideoMaxKeyFrameIntervalDurationKey: 0.5,
                AVVideoAllowFrameReorderingKey: false,
                AVVideoExpectedSourceFrameRateKey: 30,
                AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
            ],
        ])
        video.expectsMediaDataInRealTime = true
        let audio = AVAssetWriterInput(mediaType: .audio, outputSettings: [
            AVFormatIDKey: kAudioFormatMPEG4AAC,
            AVSampleRateKey: 44_100,
            AVNumberOfChannelsKey: 2,
            AVEncoderBitRateKey: 128_000,
        ])
        audio.expectsMediaDataInRealTime = true
        if w.canAdd(video) { w.add(video) }
        if w.canAdd(audio) { w.add(audio) }
        adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: video, sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
            kCVPixelBufferWidthKey as String: Self.width,
            kCVPixelBufferHeightKey as String: Self.height,
        ])
        writer = w
        videoInput = video
        audioInput = audio
    }

    override func processSampleBuffer(_ sampleBuffer: CMSampleBuffer, with type: RPSampleBufferType) {
        queue.sync {
            switch type {
            case .video: handleVideo(sampleBuffer)
            case .audioApp: handleAudio(sampleBuffer)
            default: break
            }
        }
    }

    private func handleVideo(_ sample: CMSampleBuffer) {
        guard let writer = writer, let input = videoInput, let adaptor = adaptor,
              let pixels = CMSampleBufferGetImageBuffer(sample) else { return }
        var pts = CMSampleBufferGetPresentationTimeStamp(sample)
        // Los tiempos nunca pueden ir hacia atrás (el codificador se detendría), aunque se haya repetido un cuadro.
        if lastVideo.isValid, CMTimeCompare(pts, lastVideo) <= 0 {
            pts = CMTimeAdd(lastVideo, CMTime(value: 1, timescale: 600))
        }
        if !started {
            writer.initialSegmentStartTime = pts
            guard writer.startWriting() else { return }
            writer.startSession(atSourceTime: pts)
            started = true
        }
        // Máximo 30 cuadros por segundo.
        if lastVideo.isValid, CMTimeGetSeconds(CMTimeSubtract(pts, lastVideo)) < 1.0 / 31 { return }
        guard input.isReadyForMoreMediaData, let pool = adaptor.pixelBufferPool else { return }
        var out: CVPixelBuffer?
        CVPixelBufferPoolCreatePixelBuffer(nil, pool, &out)
        guard let target = out else { return }

        var image = CIImage(cvPixelBuffer: pixels)
        if let raw = CMGetAttachment(sample, key: RPVideoSampleOrientationKey as CFString, attachmentModeOut: nil) as? NSNumber,
           let orientation = CGImagePropertyOrientation(rawValue: raw.uint32Value) {
            // ReplayKit indica hacia dónde está girada la pantalla; para enderezarla hay que girar al lado contrario.
            switch orientation {
            case .left: image = image.oriented(.right)
            case .right: image = image.oriented(.left)
            default: image = image.oriented(orientation)
            }
        }
        let canvas = CGRect(x: 0, y: 0, width: Self.width, height: Self.height)
        let scale = min(canvas.width / image.extent.width, canvas.height / image.extent.height)
        image = image.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
        image = image.transformed(by: CGAffineTransform(
            translationX: (canvas.width - image.extent.width) / 2 - image.extent.minX,
            y: (canvas.height - image.extent.height) / 2 - image.extent.minY))
        let framed = image.composited(over: CIImage(color: .black).cropped(to: canvas))
        ci.render(framed, to: target, bounds: canvas, colorSpace: CGColorSpaceCreateDeviceRGB())
        if adaptor.append(target, withPresentationTime: pts) {
            lastVideo = pts
            lastFrame = target
        }
    }

    private func handleAudio(_ sample: CMSampleBuffer) {
        guard started, let input = audioInput, input.isReadyForMoreMediaData else { return }
        input.append(sample)
    }

    func assetWriter(_ writer: AVAssetWriter, didOutputSegmentData segmentData: Data,
                     segmentType: AVAssetSegmentType, segmentReport: AVAssetSegmentReport?) {
        switch segmentType {
        case .initialization:
            server.setInit(segmentData)
        case .separable:
            let duration = segmentReport?.trackReports.first.map { CMTimeGetSeconds($0.duration) } ?? 1
            server.addSegment(segmentData, duration: duration)
        @unknown default:
            break
        }
    }
}
