#!/usr/bin/env swift
import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count == 3 else {
    fputs("usage: ocr_pages.swift RENDERED_ROOT OUTPUT_JSONL\n", stderr)
    exit(2)
}
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2])
let fm = FileManager.default
let enumerator = fm.enumerator(at: root, includingPropertiesForKeys: nil)!
var files: [URL] = []
for case let url as URL in enumerator {
    if url.pathExtension.lowercased() == "jpg" && !url.path.contains("/contact/") {
        files.append(url)
    }
}
files.sort { $0.path < $1.path }
fm.createFile(atPath: output.path, contents: nil)
let handle = try FileHandle(forWritingTo: output)
defer { try? handle.close() }

for url in files {
    guard let image = NSImage(contentsOf: url),
          let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["en-US"]
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    try? handler.perform([request])
    let observations = request.results ?? []
    let strings = observations.compactMap { $0.topCandidates(1).first?.string }
    let rel = url.path.replacingOccurrences(of: root.path + "/", with: "")
    let record: [String: Any] = ["rendered_page": rel, "ocr_lines": strings]
    let data = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys])
    handle.write(data)
    handle.write(Data([0x0A]))
}
