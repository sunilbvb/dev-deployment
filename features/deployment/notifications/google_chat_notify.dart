import 'dart:convert';
import 'dart:io';

Future<void> main(List<String> args) async {
  final Uri? webhookUri = _readWebhookUri();
  if (webhookUri == null) {
    stderr.writeln(
      '[google_chat_notify] GOOGLE_CHAT_WEBHOOK_URL not set; skipping notification.',
    );
    exitCode = 0;
    return;
  }

  final Map<String, String> parsedArgs = _parseArgs(args);
  final String status = (parsedArgs['status'] ?? 'info').trim();
  final String text = (parsedArgs['text'] ?? '').trim();
  final String title = (parsedArgs['title'] ?? '').trim();

  final String finalText = [
    if (title.isNotEmpty) title,
    if (text.isNotEmpty) text,
    if (text.isEmpty && title.isEmpty) 'Notification ($status)',
  ].join('\n');

  final HttpClient httpClient = HttpClient();
  try {
    final HttpClientRequest request = await httpClient.postUrl(webhookUri);
    request.headers.contentType = ContentType.json;
    request.add(utf8.encode(jsonEncode(<String, String>{'text': finalText})));

    final HttpClientResponse response = await request.close();
    final String body = await utf8.decodeStream(response);

    if (response.statusCode < 200 || response.statusCode >= 300) {
      stderr.writeln(
        '[google_chat_notify] Non-2xx response: ${response.statusCode}. Body: $body',
      );
      exitCode = 1;
      return;
    }
  } finally {
    httpClient.close(force: true);
  }
}

Uri? _readWebhookUri() {
  final String url =
      (Platform.environment['GOOGLE_CHAT_WEBHOOK_URL'] ?? '').trim();
  if (url.isEmpty) {
    return null;
  }

  return Uri.tryParse(url);
}

Map<String, String> _parseArgs(List<String> args) {
  final Map<String, String> result = <String, String>{};

  for (int i = 0; i < args.length; i++) {
    final String arg = args[i];
    if (!arg.startsWith('--')) {
      continue;
    }

    final String key = arg.substring(2);
    if (key.isEmpty) {
      continue;
    }

    final bool hasValue = i + 1 < args.length && !args[i + 1].startsWith('--');
    final String value = hasValue ? args[++i] : 'true';
    result[key] = value;
  }

  return result;
}
