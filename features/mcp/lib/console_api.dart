import 'dart:convert';
import 'dart:io';

/// Calls the console's REST API (docs/API.md). Replaceable in tests.
abstract class ConsoleApi {
  Future<Map<String, Object?>> call(
    String method,
    String path, {
    Map<String, String?> query = const {},
    Map<String, Object?>? body,
    String? workspace,
  });
}

/// HTTP client for the local console. The auth token is read from the
/// console's token file and is never returned to the model.
class HttpConsoleApi implements ConsoleApi {
  HttpConsoleApi({int? port, String? token})
    : _port =
          port ??
          int.tryParse(Platform.environment['DEPLOYMENT_PORT'] ?? '') ??
          18112,
      _token = token;

  final int _port;
  final String? _token;

  String _readToken() {
    if (_token != null) return _token;
    final env = Platform.environment['DEPLOYMENT_AUTH_TOKEN']?.trim() ?? '';
    if (env.isNotEmpty) return env;
    final home = Platform.environment['HOME'] ?? '';
    final file = File('$home/.config/dev-deployment/auth_token.txt');
    return file.existsSync() ? file.readAsStringSync().trim() : '';
  }

  @override
  Future<Map<String, Object?>> call(
    String method,
    String path, {
    Map<String, String?> query = const {},
    Map<String, Object?>? body,
    String? workspace,
  }) async {
    final q = {
      for (final e in query.entries)
        if (e.value != null && e.value!.isNotEmpty) e.key: e.value!,
    };
    final uri = Uri(
      scheme: 'http',
      host: '127.0.0.1',
      port: _port,
      path: path,
      queryParameters: q.isEmpty ? null : q,
    );
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 10);
    try {
      final req = await client.openUrl(method, uri);
      req.headers.set('X-API-Token', _readToken());
      if (workspace != null && workspace.isNotEmpty) {
        req.headers.set('X-Workspace', workspace);
      }
      if (body != null) {
        // Set Content-Length explicitly: the console's server does not read
        // chunked request bodies, which dart:io sends by default.
        final bytes = utf8.encode(jsonEncode(body));
        req.headers.contentType = ContentType.json;
        req.contentLength = bytes.length;
        req.add(bytes);
      }
      final res = await req.close().timeout(const Duration(seconds: 30));
      final text = await res.transform(utf8.decoder).join();
      try {
        return (jsonDecode(text) as Map).cast<String, Object?>();
      } catch (_) {
        return {'success': false, 'error': 'HTTP ${res.statusCode}'};
      }
    } on SocketException {
      return {
        'success': false,
        'error': 'Console not reachable. Start it with ./start.sh.',
      };
    } finally {
      client.close(force: true);
    }
  }
}
