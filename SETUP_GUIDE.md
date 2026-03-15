# Universal Spec Architect — Setup Guide

This MCP server enforces a rigorous, spec-driven engineering workflow (Requirements → Design → Tasks) before any code is written. It is compatible with all major MCP-enabled AI coding assistants.

Follow the instructions below for your specific IDE or assistant.

---

## 1. Cursor IDE

Cursor supports project-level and global MCP servers.

**Setup:**
1. Open your project in Cursor.
2. Create a `.cursor` directory in your project root if it doesn't exist.
3. Copy the contents of `configs/cursor/mcp.json` into `.cursor/mcp.json`.
4. Alternatively, go to **Settings > Features > MCP** and add a new server using the command: `uvx fastmcp run src/universal_spec_mcp/server.py`.

---

## 2. Windsurf IDE

Windsurf uses a global configuration file for MCP servers.

**Setup:**
1. Open Windsurf Settings (Cmd/Ctrl + Shift + P -> "Open Windsurf Settings").
2. Navigate to **Advanced → Cascade**.
3. Open your `mcp_config.json` file (usually located at `~/.codeium/windsurf/mcp_config.json`).
4. Merge the contents of `configs/windsurf/mcp_config.json` into your existing configuration.
5. Restart Windsurf.

---

## 3. VS Code (GitHub Copilot)

GitHub Copilot in VS Code supports MCP servers via the `mcp.json` configuration.

**Setup:**
1. Open your project in VS Code.
2. Create a `.vscode` directory in your project root if it doesn't exist.
3. Copy the contents of `configs/vscode/mcp.json` into `.vscode/mcp.json`.
4. Alternatively, run the command `MCP: Open User Configuration` from the Command Palette to install it globally.
5. You may be prompted to trust the server the first time you use it in Copilot Chat.

---

## 4. Claude Desktop

Claude Desktop supports global MCP servers.

**Setup:**
1. Open your Claude Desktop configuration file:
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
2. Merge the contents of `configs/claude/claude_desktop_config.json` into your configuration.
3. Restart Claude Desktop.

---

## 5. Cline (VS Code Extension)

Cline stores its MCP settings separately from the main VS Code settings.

**Setup:**
1. Click on the Cline icon in the VS Code sidebar.
2. Open the menu (⋮) in the top right corner of the Cline panel.
3. Select **"MCP Servers"** from the dropdown menu.
4. This will open `cline_mcp_settings.json`. Merge the contents of `configs/cline/cline_mcp_settings.json` into this file.
5. Save the file; Cline will automatically detect and connect to the server.

---

## 6. IBM Bob

IBM Bob supports project-level MCP configuration and custom modes.

**Setup:**
1. Copy the entire `.bob/` directory from this repository into your project root.
2. This includes the `mcp.json` configuration, the "Spec Architect" custom mode, and the steering templates.
3. Switch to the **Spec Architect** mode in the Bob UI to begin the workflow.
