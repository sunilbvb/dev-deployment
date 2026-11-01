// MCP server (stdio) for the Dev Deployment Console.
//
// Run:  dart run bin/server.dart      (console must be running: ./start.sh)
// Build: dart compile exe bin/server.dart -o dev-deployment-mcp
// Env:  DEPLOYMENT_PORT (default 18112), DEPLOYMENT_AUTH_TOKEN (optional)
import 'dart:io' as io;

import 'package:dart_mcp/stdio.dart';
import 'package:dev_deployment_mcp/console_api.dart';
import 'package:dev_deployment_mcp/server.dart';

void main() {
  DeploymentMcpServer(
    stdioChannel(input: io.stdin, output: io.stdout),
    api: HttpConsoleApi(),
  );
}
