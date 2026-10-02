import 'dart:convert';
import 'dart:io';

/// Clean formatting of repo path for logs
String repoLabel(String repoRoot) {
  final parts = Directory(
    repoRoot,
  ).absolute.uri.pathSegments.where((p) => p.isNotEmpty).toList();
  if (parts.length >= 2) {
    return '${parts[parts.length - 2]}/${parts.last}';
  }
  return repoRoot;
}

/// Final, easy-to-scan record of what the release produced.
Future<void> printReleaseSummary({
  required String tagName,
  required String repoRoot,
  required bool pushed,
}) async {
  final commit = await Process.run('git', ['rev-parse', '--short', '$tagName^{commit}'], workingDirectory: repoRoot);
  final branch = await Process.run('git', ['branch', '--show-current'], workingDirectory: repoRoot);
  final remote = await Process.run('git', ['remote', 'get-url', 'origin'], workingDirectory: repoRoot);
  String clean(ProcessResult r) => r.exitCode == 0 ? r.stdout.toString().trim() : '';
  print('');
  print('══════════════════ RELEASE SUMMARY ══════════════════');
  print('   Tag:        $tagName');
  print('   Commit:     ${clean(commit).isEmpty ? '(unknown)' : clean(commit)}');
  print('   Branch:     ${clean(branch).isEmpty ? '(detached)' : clean(branch)}');
  print('   Repository: ${repoLabel(repoRoot)}');
  print('   Remote:     ${clean(remote).isEmpty ? '(none configured)' : clean(remote)}');
  print('   Pushed:     ${pushed ? 'yes' : 'no (local only)'}');
  print('═════════════════════════════════════════════════════');
}

/// Dispatch chat notification to Google Chat / Slack webhook
Future<void> dispatchChatNotification(
  String appName,
  String version,
  String tagName,
  String changelog,
) async {
  final webhookUrl =
      Platform.environment['GOOGLE_CHAT_WEBHOOK_URL'] ??
      Platform.environment['SLACK_WEBHOOK_URL'];
  if (webhookUrl == null || webhookUrl.isEmpty) {
    print('ℹ️ No GOOGLE_CHAT_WEBHOOK_URL configured. Skipping chat broadcast.');
    return;
  }

  print('📢 Sending release notification to chat webhook...');
  try {
    final payload = json.encode({
      "text": "🚀 *New Release: $appName $version* ($tagName)\n\n$changelog",
    });
    final client = HttpClient();
    final req = await client.postUrl(Uri.parse(webhookUrl));
    req.headers.set('Content-Type', 'application/json; charset=UTF-8');
    req.write(payload);
    final resp = await req.close();
    if (resp.statusCode == 200) {
      print('✅ Release notification sent to chat!');
    }
  } catch (e) {
    print('⚠️ Chat webhook error: $e');
  }
}
