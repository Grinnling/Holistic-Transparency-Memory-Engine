#!/bin/bash
# Run rich_chat with panel UI enabled

echo "Starting rich_chat with Panel UI..."
echo "Set RICH_PANEL_UI=true to enable panel layout"
echo ""

export RICH_PANEL_UI=true
python3 rich_chat.py --auto-start