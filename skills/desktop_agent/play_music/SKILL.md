# Skill: play_music

## Purpose

Use this skill when the user wants the desktop agent to play a song in a desktop music application.

## Execution Rules

1. Identify the target music application and resolve its executable path.
2. Launch the application and make sure the correct window is available.
3. Locate the search entry for the requested song.
4. Enter the song title and submit the search.
5. Select the correct result and start playback.
6. Verify whether playback has really started.
7. If any required desktop-control tool is unavailable, stop and report the missing tool clearly.

## Constraints

- Do not guess application paths.
- Do not claim playback success without an explicit verification step.
- Prefer factual status updates over narrative explanations.
- Keep the final answer concise and execution-oriented.
