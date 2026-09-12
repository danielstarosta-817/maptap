#!/bin/bash
# Take a freshly exported WhatsApp chat, rebuild the standings, publish.
#
#   ./scripts/update.sh
#
# Drop the export anywhere in whatsapp_chat/ — the .txt, or the .zip AirDrop gives you —
# and run this. It picks the newest one, checks it looks sane, rebuilds, commits and pushes.
# scripts/install-watcher.sh makes macOS run it for you whenever a file lands there.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
DROP="$ROOT/whatsapp_chat"
CHAT="$DROP/chat.txt"

say() { printf '%s\n' "$*"; }
notify() {   # a desktop notification when run unattended; harmless in a terminal
  [ -n "${MAPTAP_QUIET:-}" ] && return 0
  osascript -e "display notification \"$2\" with title \"MapTap\" subtitle \"$1\"" 2>/dev/null
}
die() { say "ERROR: $*"; notify "Update failed" "$*"; exit 1; }

[ -d "$DROP" ] || die "no whatsapp_chat/ folder"

# --- find the newest export that is not already chat.txt ---------------------
# ls -t is newest-first and behaves the same on macOS and Linux, which matters because
# `stat` does not: -f means one thing on BSD and something else entirely on GNU.
newest=""
while IFS= read -r f; do
  case "$(basename "$f")" in
    chat.txt|chat.md|_*) continue;;          # our own files, not a dropped export
  esac
  [ -f "$f" ] || continue
  newest="$f"; break
done < <(ls -t "$DROP"/*.txt "$DROP"/*.zip 2>/dev/null)

if [ -n "$newest" ]; then
  say "found export: $(basename "$newest")"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  if [[ "$newest" == *.zip ]]; then
    unzip -qo "$newest" -d "$tmp" || die "could not unzip $(basename "$newest")"
    inner="$(find "$tmp" -name '*.txt' -type f | head -1)"
    [ -n "$inner" ] || die "no .txt inside that zip"
  else
    inner="$newest"
  fi

  # --- sanity check before overwriting anything ------------------------------
  count_results() { grep -c 'Final score:' "$1" 2>/dev/null | head -1; }
  new_count=$(count_results "$inner"); new_count=${new_count:-0}
  [ "$new_count" -gt 0 ] || die "that file has no MapTap results in it — wrong chat?"
  if [ -f "$CHAT" ]; then
    old_count=$(count_results "$CHAT"); old_count=${old_count:-0}
    if [ "$new_count" -lt "$old_count" ]; then
      die "new export has $new_count results, current has $old_count — refusing to go backwards"
    fi
    say "results: $old_count -> $new_count"
  else
    say "results: $new_count"
  fi

  cp "$inner" "$CHAT" || die "could not write chat.txt"
  # keep the folder tidy so the next run does not re-import the same file
  [ "$newest" != "$CHAT" ] && rm -f "$newest"
else
  say "no new export dropped; rebuilding from the current chat.txt"
  [ -f "$CHAT" ] || die "nothing to build from — export the chat and drop it in whatsapp_chat/"
fi

# --- rebuild -----------------------------------------------------------------
out="$(python3 scripts/build.py 2>&1)" || { say "$out"; die "build failed"; }
say "$out"

# --- publish -----------------------------------------------------------------
# Only the files this pipeline owns. The watcher fires on its own, so it must never sweep
# up whatever else happens to be uncommitted in the repo at the time.
OWNED=(index.html data)
if git diff --quiet -- "${OWNED[@]}" && git diff --cached --quiet -- "${OWNED[@]}"; then
  say "no change to publish"
  notify "Already up to date" "Nothing new in the export."
  exit 0
fi

git add -- "${OWNED[@]}" || die "git add failed"
git commit -q -m "standings: $(date -u +%Y-%m-%d)" || die "git commit failed"

# set MAPTAP_NO_PUSH=1 to stop here and review the commit before publishing
if [ -n "${MAPTAP_NO_PUSH:-}" ]; then
  say "committed, not pushed (MAPTAP_NO_PUSH is set). Run 'git push' when you are happy."
  notify "Committed, not pushed" "Review it, then git push."
  exit 0
fi

if git push -q 2>/dev/null; then
  lead="$(printf '%s\n' "$out" | sed -n 's/^leader: //p')"
  say "pushed."
  notify "Standings updated" "${lead:-pushed}"
else
  say "committed, but the push failed — run 'git push' yourself to see why."
  notify "Committed, not pushed" "Run git push in the repo."
  exit 1
fi
