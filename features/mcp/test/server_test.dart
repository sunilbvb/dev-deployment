import 'dart:convert';
import 'dart:io';


import 'package:dev_deployment_mcp/console_api.dart';
import 'package:dev_deployment_mcp/server.dart';
import 'package:test/test.dart';

class FakeApi implements ConsoleApi {
  final calls = <Map<String, Object?>>[];
  Map<String, Object?> reply = {'success': true};

  @override
  Future<Map<String, Object?>> call(
    String method,
    String path, {
    Map<String, String?> query = const {},
    Map<String, Object?>? body,
    String? workspace,
  }) async {
    calls.add({
      'method': method,
      'path': path,
      'query': query,
      'body': body,
      'workspace': workspace,
    });
    return Map.of(reply);
  }
}

void main() {
  late FakeApi api;
  setUp(() => api = FakeApi());
  httpBodyTests();

  test('run_command forwards only template id, flavor and workspace', () async {
    await callTool(api, 'run_command', {
      'app': 'a',
      'templateId': 'build_aab',
      'flavor': 'prod',
      'workspace': '/p',
      'cmd': 'rm -rf /',
    });
    final c = api.calls.single;
    expect([c['method'], c['path'], c['workspace']],
        ['POST', '/api/deployment/execute', '/p']);
    expect(c['body'], {
      'app': 'a',
      'templateId': 'build_aab',
      'flavor': 'prod',
      'confirmed': false,
    });
  });

  test('confirmed defaults to false', () async {
    await callTool(api, 'run_command', {'app': 'a', 'templateId': 't'});
    expect((api.calls.single['body'] as Map)['confirmed'], false);
  });

  test('release notes are forwarded when present', () async {
    await callTool(api, 'run_command', {
      'app': 'a',
      'templateId': 't',
      'releaseNotes': {'en-US': 'Fixes'},
    });
    expect((api.calls.single['body'] as Map)['releaseNotes'], {'en-US': 'Fixes'});
  });

  test('history limit is capped at 50', () async {
    await callTool(api, 'history', {'limit': 9999});
    expect((api.calls.single['query'] as Map)['limit'], '50');
  });

  test('get_job truncates long logs', () async {
    api.reply = {'success': true, 'log': 'x' * 20000};
    final res = await callTool(api, 'get_job', {'jobId': '1'});
    expect((res['log'] as String).length, lessThan(maxLogChars + 50));
  });

  test('unknown tool throws', () {
    expect(() => callTool(api, 'nope', {}), throwsArgumentError);
  });
}

void httpBodyTests() {
  test('HttpConsoleApi sends POST bodies with Content-Length, not chunked',
      () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    addTearDown(() => server.close(force: true));
    String? length, encoding, gotBody;
    server.listen((r) async {
      length = r.headers.value('content-length');
      encoding = r.headers.value('transfer-encoding');
      gotBody = await utf8.decoder.bind(r).join();
      r.response
        ..write('{"success": true}')
        ..close();
    });
    final real = HttpConsoleApi(port: server.port, token: 't');
    await real.call('POST', '/x', body: {'app': 'a'});
    expect(length, '${utf8.encode('{"app":"a"}').length}');
    expect(encoding, isNull);
    expect(gotBody, '{"app":"a"}');
  });
}
