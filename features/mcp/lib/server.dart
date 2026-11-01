import 'dart:async';
import 'dart:convert';

import 'package:dart_mcp/server.dart';

import 'console_api.dart';

const maxLogChars = 8000;
const _d = '/api/deployment/';

/// Optional project path, sent as `X-Workspace` (per-request project).
final _workspace = Schema.string(
  description:
      'Absolute project path. Omit to use the console\'s active project.',
);

ObjectSchema _schema(
  Map<String, Schema> props, [
  List<String> required = const [],
]) => Schema.object(
  properties: {'workspace': _workspace, ...props},
  required: required,
);

/// MCP server that forwards fixed tools to the console's REST API.
///
/// Rule 4: `run_command` forwards only a template id; the console validates
/// it. No command text from the model is ever executed here.
base class DeploymentMcpServer extends MCPServer with ToolsSupport {
  DeploymentMcpServer(super.channel, {required this.api})
    : super.fromStreamChannel(
        implementation: Implementation(
          name: 'dev-deployment-console',
          version: '0.2.0',
        ),
        instructions:
            'Build and release mobile apps through the Dev Deployment Console. '
            'Call list_commands before run_command. Only set confirmed=true '
            'after the user explicitly approves a PROD store deploy.',
      ) {
    for (final t in _tools) {
      registerTool(t.tool, (req) => _run(t.name, req.arguments ?? const {}));
    }
  }

  final ConsoleApi api;

  late final _tools = <_Def>[
    _Def('list_projects', 'List projects added to the console.',
        Schema.object(), true),
    _Def('list_apps',
        'List deployable apps and packages detected in the project.',
        _schema({}), true),
    _Def(
      'list_commands',
      'List runnable build/upload commands (template ids, flavors) for an '
          'app. Call before run_command.',
      _schema({'app': Schema.string()}, ['app']),
      true,
    ),
    _Def(
      'run_command',
      'Start a build/upload job from a template id returned by list_commands. '
          'Returns a job id; poll get_job. PROD store deploys need '
          'confirmed=true, which must only be set after the user explicitly '
          'approves.',
      _schema({
        'app': Schema.string(),
        'templateId': Schema.string(),
        'flavor': Schema.string(),
        'confirmed': Schema.bool(),
        'releaseNotes': Schema.object(
          description: 'Optional {locale: text}.',
          additionalProperties: Schema.string(),
        ),
      }, ['app', 'templateId']),
      false,
    ),
    _Def('get_job', 'Status and recent log output of a job.',
        _schema({'jobId': Schema.string()}, ['jobId']), true),
    _Def('stop_job', 'Stop a running job.',
        _schema({'jobId': Schema.string()}, ['jobId']), false),
    _Def('running_jobs', 'List jobs currently running.', _schema({}), true),
    _Def(
      'history',
      'Past runs, newest first.',
      _schema({
        'app': Schema.string(),
        'flavor': Schema.string(),
        'status': Schema.string(),
        'limit': Schema.int(),
      }),
      true,
    ),
    _Def(
      'doctor',
      'Pre-flight diagnostics (SDKs, signing, credentials) for an app/flavor.',
      _schema({'app': Schema.string(), 'flavor': Schema.string()}, ['app']),
      true,
    ),
  ];

  Future<CallToolResult> _run(String name, Map<String, Object?> a) async {
    final def = _tools.firstWhere((t) => t.name == name);
    final missing = [
      for (final r in def.tool.inputSchema.required ?? const <String>[])
        if (a[r] == null) r,
    ];
    if (missing.isNotEmpty) {
      return CallToolResult(
        content: [TextContent(text: 'Missing argument(s): ${missing.join(', ')}')],
        isError: true,
      );
    }
    final res = await callTool(api, name, a);
    return CallToolResult(
      content: [TextContent(text: const JsonEncoder.withIndent('  ').convert(res))],
      isError: res['success'] == false,
    );
  }
}

class _Def {
  _Def(this.name, String description, ObjectSchema schema, bool readOnly)
    : tool = Tool(
        name: name,
        description: description,
        inputSchema: schema,
        annotations: ToolAnnotations(
          readOnlyHint: readOnly,
          destructiveHint: !readOnly,
          openWorldHint: false,
        ),
      );
  final String name;
  final Tool tool;
}

/// Keeps only the tail of long logs so one poll cannot flood the model.
Map<String, Object?> trimJob(Map<String, Object?> res) {
  for (final k in res.keys.toList()) {
    final v = res[k];
    if (v is String && v.length > maxLogChars) {
      res[k] = '...[truncated]\n${v.substring(v.length - maxLogChars)}';
    } else if (v is Map && k == 'job') {
      res[k] = trimJob(v.cast<String, Object?>());
    }
  }
  return res;
}

/// Maps a tool call to the console API. Throws [ArgumentError] on unknown names.
Future<Map<String, Object?>> callTool(
  ConsoleApi api,
  String name,
  Map<String, Object?> a,
) {
  final ws = a['workspace'] as String?;
  String? s(String k) => a[k] as String?;
  switch (name) {
    case 'list_projects':
      return api.call('GET', '${_d}workspaces');
    case 'list_apps':
      return api.call('GET', '${_d}apps', workspace: ws);
    case 'list_commands':
      return api.call('GET', '${_d}commands',
          query: {'app': s('app')}, workspace: ws);
    case 'run_command':
      return api.call('POST', '${_d}execute', workspace: ws, body: {
        'app': a['app'],
        'templateId': a['templateId'],
        'flavor': s('flavor') ?? '',
        'confirmed': a['confirmed'] == true,
        if (a['releaseNotes'] is Map && (a['releaseNotes'] as Map).isNotEmpty)
          'releaseNotes': a['releaseNotes'],
      });
    case 'get_job':
      return api
          .call('GET', '${_d}job', query: {'id': s('jobId')}, workspace: ws)
          .then(trimJob);
    case 'stop_job':
      return api.call('POST', '${_d}stop',
          body: {'jobId': a['jobId']}, workspace: ws);
    case 'running_jobs':
      return api.call('GET', '${_d}running-jobs', workspace: ws);
    case 'history':
      final limit = ((a['limit'] as num?)?.toInt() ?? 10).clamp(1, 50);
      return api.call('GET', '${_d}history', workspace: ws, query: {
        'app': s('app'),
        'flavor': s('flavor'),
        'status': s('status'),
        'limit': '$limit',
      });
    case 'doctor':
      return api.call('GET', '${_d}doctor',
          query: {'app': s('app'), 'flavor': s('flavor')}, workspace: ws);
  }
  throw ArgumentError('Unknown tool: $name');
}
