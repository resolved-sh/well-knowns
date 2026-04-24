# Claude Code

c:
	claude

# start remote control with Claude
crc:
	claude --remote-control

crc-yolo:
	claude --remote-control --dangerously-skip-permissions --effort high

.PHONY: c crc crc-yolo