import SwiftUI

// MARK: - Markdown Renderer

struct MarkdownRenderer: View {
    let text: String
    let isUser: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            ForEach(Array(parseBlocks(text).enumerated()), id: \.offset) { _, block in
                renderBlock(block)
            }
        }
    }

    // MARK: - Block Types

    private enum MarkdownBlock {
        case paragraph(String)
        case heading(Int, String)
        case codeBlock(String, String)  // language, code
        case bulletList([String])
        case numberedList([String])
        case blockquote(String)
        case horizontalRule
    }

    // MARK: - Parser

    private func parseBlocks(_ text: String) -> [MarkdownBlock] {
        var blocks: [MarkdownBlock] = []
        let lines = text.components(separatedBy: "\n")
        var i = 0

        while i < lines.count {
            let line = lines[i]

            // Code block
            if line.hasPrefix("```") {
                let language = String(line.dropFirst(3)).trimmingCharacters(in: .whitespaces)
                var codeLines: [String] = []
                i += 1
                while i < lines.count && !lines[i].hasPrefix("```") {
                    codeLines.append(lines[i])
                    i += 1
                }
                blocks.append(.codeBlock(language, codeLines.joined(separator: "\n")))
                i += 1
                continue
            }

            // Heading
            if line.hasPrefix("### ") {
                blocks.append(.heading(3, String(line.dropFirst(4))))
                i += 1
                continue
            }
            if line.hasPrefix("## ") {
                blocks.append(.heading(2, String(line.dropFirst(3))))
                i += 1
                continue
            }
            if line.hasPrefix("# ") {
                blocks.append(.heading(1, String(line.dropFirst(2))))
                i += 1
                continue
            }

            // Horizontal rule
            if line.trimmingCharacters(in: .whitespaces).count >= 3 &&
               line.trimmingCharacters(in: .whitespaces).allSatisfy({ $0 == "-" || $0 == "*" || $0 == "_" }) &&
               Set(line.trimmingCharacters(in: .whitespaces)).count == 1 {
                blocks.append(.horizontalRule)
                i += 1
                continue
            }

            // Blockquote
            if line.hasPrefix("> ") {
                var quoteLines: [String] = []
                while i < lines.count && lines[i].hasPrefix("> ") {
                    quoteLines.append(String(lines[i].dropFirst(2)))
                    i += 1
                }
                blocks.append(.blockquote(quoteLines.joined(separator: "\n")))
                continue
            }

            // Bullet list
            if line.hasPrefix("- ") || line.hasPrefix("* ") {
                var items: [String] = []
                while i < lines.count && (lines[i].hasPrefix("- ") || lines[i].hasPrefix("* ")) {
                    items.append(String(lines[i].dropFirst(2)))
                    i += 1
                }
                blocks.append(.bulletList(items))
                continue
            }

            // Numbered list
            if let _ = line.range(of: #"^\d+\.\s"#, options: .regularExpression) {
                var items: [String] = []
                while i < lines.count,
                      let range = lines[i].range(of: #"^\d+\.\s"#, options: .regularExpression) {
                    items.append(String(lines[i][range.upperBound...]))
                    i += 1
                }
                blocks.append(.numberedList(items))
                continue
            }

            // Empty line
            if line.trimmingCharacters(in: .whitespaces).isEmpty {
                i += 1
                continue
            }

            // Paragraph — collect consecutive non-special lines
            var paraLines: [String] = []
            while i < lines.count {
                let l = lines[i]
                if l.isEmpty || l.hasPrefix("```") || l.hasPrefix("#") || l.hasPrefix("> ") ||
                   l.hasPrefix("- ") || l.hasPrefix("* ") ||
                   l.range(of: #"^\d+\.\s"#, options: .regularExpression) != nil {
                    break
                }
                paraLines.append(l)
                i += 1
            }
            if !paraLines.isEmpty {
                blocks.append(.paragraph(paraLines.joined(separator: " ")))
            }
        }

        return blocks
    }

    // MARK: - Renderers

    @ViewBuilder
    private func renderBlock(_ block: MarkdownBlock) -> some View {
        switch block {
        case .paragraph(let text):
            inlineMarkdown(text)

        case .heading(let level, let text):
            Text(text)
                .font(.system(size: headingSize(level), weight: .bold))
                .foregroundColor(isUser ? .white : CipherTheme.textPrimary)
                .padding(.top, Spacing.xxs)

        case .codeBlock(let language, let code):
            CodeBlockView(language: language, code: code)

        case .bulletList(let items):
            VStack(alignment: .leading, spacing: Spacing.xxs) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                    HStack(alignment: .top, spacing: Spacing.sm) {
                        Text("\u{2022}")
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(isUser ? .white.opacity(0.7) : CipherTheme.accent)
                        inlineMarkdown(item)
                    }
                }
            }

        case .numberedList(let items):
            VStack(alignment: .leading, spacing: Spacing.xxs) {
                ForEach(Array(items.enumerated()), id: \.offset) { index, item in
                    HStack(alignment: .top, spacing: Spacing.sm) {
                        Text("\(index + 1).")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(isUser ? .white.opacity(0.7) : CipherTheme.accent)
                            .frame(width: 20, alignment: .trailing)
                        inlineMarkdown(item)
                    }
                }
            }

        case .blockquote(let text):
            HStack(spacing: 0) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(CipherTheme.accent.opacity(0.5))
                    .frame(width: 3)

                Text(text)
                    .font(.system(size: 14))
                    .italic()
                    .foregroundColor(isUser ? .white.opacity(0.85) : CipherTheme.textSecondary)
                    .padding(.leading, Spacing.md)
            }
            .padding(.vertical, Spacing.xxs)

        case .horizontalRule:
            Divider()
                .background(CipherTheme.border)
                .padding(.vertical, Spacing.sm)
        }
    }

    private func inlineMarkdown(_ text: String) -> some View {
        Text(parseInline(text))
            .font(.system(size: 15, weight: .regular))
            .foregroundColor(isUser ? .white : CipherTheme.textPrimary)
            .lineSpacing(3)
    }

    private func parseInline(_ text: String) -> AttributedString {
        var result = AttributedString()
        var current = text

        while !current.isEmpty {
            // Bold + Italic
            if let range = current.range(of: #"\*\*\*(.+?)\*\*\*"#, options: .regularExpression) {
                let before = String(current[current.startIndex..<range.lowerBound])
                let match = String(current[range]).dropFirst(3).dropLast(3)

                result += AttributedString(before)
                var attr = AttributedString(String(match))
                attr.font = .system(size: 15, weight: .bold).italic()
                result += attr
                current = String(current[range.upperBound...])
                continue
            }

            // Bold
            if let range = current.range(of: #"\*\*(.+?)\*\*"#, options: .regularExpression) {
                let before = String(current[current.startIndex..<range.lowerBound])
                let match = String(current[range]).dropFirst(2).dropLast(2)

                result += AttributedString(before)
                var attr = AttributedString(String(match))
                attr.font = .system(size: 15, weight: .bold)
                result += attr
                current = String(current[range.upperBound...])
                continue
            }

            // Italic
            if let range = current.range(of: #"\*(.+?)\*"#, options: .regularExpression) {
                let before = String(current[current.startIndex..<range.lowerBound])
                let match = String(current[range]).dropFirst(1).dropLast(1)

                result += AttributedString(before)
                var attr = AttributedString(String(match))
                attr.font = .system(size: 15).italic()
                result += attr
                current = String(current[range.upperBound...])
                continue
            }

            // Inline code
            if let range = current.range(of: #"`(.+?)`"#, options: .regularExpression) {
                let before = String(current[current.startIndex..<range.lowerBound])
                let match = String(current[range]).dropFirst(1).dropLast(1)

                result += AttributedString(before)
                var attr = AttributedString(String(match))
                attr.font = .system(size: 13, design: .monospaced)
                attr.backgroundColor = isUser ? .white.opacity(0.15) : CipherTheme.surface
                result += attr
                current = String(current[range.upperBound...])
                continue
            }

            // No more patterns
            result += AttributedString(current)
            break
        }

        return result
    }

    private func headingSize(_ level: Int) -> CGFloat {
        switch level {
        case 1: return 22
        case 2: return 19
        case 3: return 16
        default: return 15
        }
    }
}

// MARK: - Code Block View

struct CodeBlockView: View {
    let language: String
    let code: String
    @State private var copied = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header bar
            HStack {
                Text(language.isEmpty ? "code" : language)
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundColor(CipherTheme.textTertiary)
                    .textCase(.uppercase)

                Spacer()

                Button(action: copyCode) {
                    HStack(spacing: 4) {
                        Image(systemName: copied ? "checkmark" : "doc.on.doc")
                            .font(.system(size: 11, weight: .medium))

                        Text(copied ? "Copied" : "Copy")
                            .font(.system(size: 11, weight: .medium))
                    }
                    .foregroundColor(copied ? CipherTheme.success : CipherTheme.textTertiary)
                }
            }
            .padding(.horizontal, Spacing.md)
            .padding(.vertical, Spacing.sm)
            .background(Color.black.opacity(0.3))

            // Code content
            ScrollView(.horizontal, showsIndicators: false) {
                Text(code)
                    .font(.system(size: 13, design: .monospaced))
                    .foregroundColor(CipherTheme.textPrimary)
                    .padding(Spacing.md)
            }
        }
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.sm)
                .fill(Color(hex: "0D1117"))
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.sm)
                        .stroke(CipherTheme.border, lineWidth: 0.5)
                )
        )
    }

    private func copyCode() {
        UIPasteboard.general.string = code
        withAnimation {
            copied = true
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            withAnimation {
                copied = false
            }
        }
    }
}

#Preview {
    ScrollView {
        MarkdownRenderer(
            text: """
            # Hello World

            This is a **bold** and *italic* test with `inline code`.

            ## Code Example

            ```swift
            func greet(_ name: String) -> String {
                return "Hello, \\(name)!"
            }
            ```

            Here's a list:
            - First item with **bold**
            - Second item with `code`
            - Third item

            > This is a blockquote that contains some wisdom.

            And numbered:
            1. Step one
            2. Step two
            3. Step three
            """,
            isUser: false
        )
        .padding()
    }
    .background(CipherTheme.background)
}
