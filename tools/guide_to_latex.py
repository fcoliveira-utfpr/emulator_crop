"""Section S5 of the supplementary material (guide to the web application) from docs/guide.md.

    python tools/guide_to_latex.py artigo/supplementary.tex

Converts the Markdown subset used in the guide (## headings with <a id> anchors, paragraphs, bold, italic,
code, links, nested bullet and numbered lists with continuation paragraphs) to LaTeX and replaces the text of
S5 in the given file, from the first paragraph of the guide (the line starting with the CropEmu link) to
the next \\section (or \\end{document} if S5 is the last section). Links to other sections of the guide become "text~(Section~\\ref{guide-<id>})". The title,
the "Versão em português" link and the table of contents of the Markdown file are skipped.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = r"\href{https://fcoliveira-utfpr.github.io/emulator_crop/}{CropEmu}"
END = r"\end{document}"
NEXT = re.compile(r"(\\clearpage\s*)?\\section\*?\{")


def escape(s: str) -> str:
    out = []
    for ch in s:
        out.append({"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "$": r"\$",
                    "~": r"\textasciitilde{}", "^": r"\^{}", "{": r"\{", "}": r"\}"}.get(ch, ch))
    return "".join(out)


def inline(s: str) -> str:
    """Inline Markdown -> LaTeX (links and code are protected before the emphasis)."""
    keep = []

    def hold(text):
        keep.append(text)
        return f"\x00{len(keep) - 1}\x00"

    s = re.sub(r"`([^`]+)`", lambda m: hold(r"\texttt{" + escape(m.group(1)) + "}"), s)

    def link(m):
        text, url = m.group(1), m.group(2)
        if url.startswith("#"):
            return hold(inline_plain(text) + r"~(Section~\ref{guide-" + url[1:] + "})")
        return hold(r"\href{" + url.replace("%", r"\%").replace("#", r"\#") + "}{" + inline_plain(text) + "}")

    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, s)
    s = escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\\emph{\1}", s)
    return re.sub("\x00(\\d+)\x00", lambda m: keep[int(m.group(1))], s)


def inline_plain(s: str) -> str:
    s = escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", s)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\\emph{\1}", s)


ITEM = re.compile(r"^(\s*)(-|\d+\.)\s+(.*)$")


def convert(md: str) -> str:
    lines = md.splitlines()
    # skip the title, the language link and the table of contents: start at the first paragraph,
    # keep paragraphs until "**Contents**", then resume at the first anchor
    out, para, stack, anchor = [], [], [], None
    i0 = next(i for i, l in enumerate(lines) if l.startswith("[CropEmu]"))
    body = []
    i = i0
    while i < len(lines) and not lines[i].startswith("**Contents**"):
        if not lines[i].startswith("[Versão"):
            body.append(lines[i])
        i += 1
    while i < len(lines) and not lines[i].startswith("<a id="):
        i += 1
    body += lines[i:]

    def flush():
        if para:
            text = inline(" ".join(p.strip() for p in para))
            out.append((r"\par " if stack else "") + text)
            if not stack:
                out.append("")
            para.clear()

    def close_to(level):
        while len(stack) > level:
            flush()
            out.append(r"\end{" + stack.pop()[1] + "}")
            if not stack:
                out.append("")

    for line in body:
        m_anchor = re.match(r'<a id="([^"]+)"></a>', line.strip())
        if m_anchor:
            flush(); close_to(0)
            anchor = m_anchor.group(1)
            continue
        if line.startswith("## "):
            flush(); close_to(0)
            out.append(r"\subsection{" + inline(line[3:].strip()) + "}" + (r"\label{guide-" + anchor + "}" if anchor else ""))
            anchor = None
            continue
        if not line.strip():
            flush()
            continue
        m = ITEM.match(line)
        depth = (len(line) - len(line.lstrip()) + 1) // 3          # 3-space indentation per list level
        if m:
            flush()
            level = depth + 1
            env = "itemize" if m.group(2) == "-" else "enumerate"
            close_to(level)
            if len(stack) < level:
                if out and out[-1] == "":
                    out.pop()
                out.append(r"\begin{" + env + "}")
                stack.append((level, env))
            out.append(r"\item " + inline(m.group(3)))
            continue
        if stack and not para:                            # a paragraph after a list item: it closes the
            close_to(depth)                               # lists deeper than its indentation (0: all)
        para.append(line)
    flush(); close_to(0)
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artigo" / "supplementary.tex"
    tex = target.read_text(encoding="utf8")
    # S5 ends at the next section (S6, S7...) or, if it is the last one, at \end{document}; a \clearpage
    # right before that section is kept with it
    a = tex.index(START)
    m = NEXT.search(tex, a)
    b = m.start() if m else tex.rindex(END)
    new = convert((ROOT / "docs" / "guide.md").read_text(encoding="utf8"))
    target.write_text(tex[:a] + new + "\n\n" + tex[b:], encoding="utf8", newline="\n")
    print(f"S5 rewritten from docs/guide.md ({len(new.splitlines())} lines) -> {target}")


if __name__ == "__main__":
    main()
