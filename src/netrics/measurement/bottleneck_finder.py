"""Detect a bottlenecked link along the speedtest path for Ookla or NDT7."""
import json
import subprocess

from schema import Optional, Or

from netrics import task

from .common import require_net


PARAMS = task.schema.extend('bottleneck-finder', {
    # exec: ndt7-client executable name or path
    Optional('exec', default='netrics-bottleneck-finder'): task.schema.Command(
        error='exec: must be an executable on PATH or file system absolute path to executable'
    ),

    Optional('idleTime', default='10'): task.schema.PositiveIntStr('idleTime', 'milliseconds'),

    Optional('maxTTL', default='5'): task.schema.NaturalStr('maxTTL'),

    Optional('pingType', default='udp'): str,

    Optional('toolType', default='ndt'): str,

    # timeout: seconds after which test is canceled
    # (0, None, False, etc. to disable timeout)
    Optional('timeout', default=300): Or(task.schema.GTZero(),
                                        task.schema.falsey,
                                        error='timeout: seconds greater than zero or '
                                              'falsey to disable'),
})

@task.param.require(PARAMS)
@require_net
def main(params):
    """
    Locate the bottlenecked link along the path of an NDT7/Ookla speedtest.

    The local network, and then Internet hosts (as configured in global
    defaults), are queried first, to ensure network operation and
    internet accessibility. (See: `require_net`.)

    The bottleneck-finder binary is then executed.

    This binary is presumed to be accessible via PATH at `tslp-bottleneck-finder`.
    This PATH look-up name is configurable, and may be replaced with the
    absolute file system path, instead (`exec`).

    Should the test not return within `timeout` seconds, an error
    is returned. (This may be disabled by setting a "falsey" timeout
    value.)
    """
    try:
        proc = subprocess.run(
            (
                params.exec,
                '-i', params.idleTime,
                '-m', params.maxTTL,
                '-p', params.pingType,
                '-t', params.toolType
            ),
            timeout=(params.timeout or None),
            capture_output=True,
            text=True
        )
    except subprocess.TimeoutExpired as exc:
        task.log.critical(
            cmd=exc.cmd,
            elapsed=exc.timeout,
            stdout=exc.stdout,
            stderr=exc.stderr,
            status='timeout',
        )
        return task.status.timeout

    results = parse_output(proc.stdout)
    task.result.write(results,
                label=params.result.label,
                annotate=params.result.annotate,
                extend=None)

    return task.status.success


def parse_output(output):
    """
    Parse the output of the binary. Returns a `dict` of the following form:

    {
            'download': float,
            'upload': float,
            'jitter': float,
            'latency': float,
            ...
            'meta': {
                'total_bytes_consumed': float,
                'url': str,
            },
            'tslp: {
                'metadata': {
                    'startTime': int,
                    'endTime': int,
                    'interface': {
                        'name': str,
                        'addr': [
                            str,
                            str
                        ]
                    },
                    'speedtest': {
                        'tool': str,
                        'serverIP': str,
                        'startTime': int,
                        'endTime': int
                    },
                    'ping': {
                        'type': str,
                        'startTime': int,
                        'endTime': int
                    },
                    'capFile': str
                },
                'ping': {
                    '1': {
                        'ttl': int,
                        'round': int,
                        'replyIP': str,
                        'sendTime': int,
                        'recvTime': int,
                        'rtt': float,
                        'icmpSeqNo': int,
                        'udpDestPort': int
                    },
                    ...
                }
            }
        }

    """
    if not output:
        task.log.error(error="None", msg="Output is none")
        return None

    try:
        result = json.loads(output)
    except (KeyError, ValueError, TypeError) as exc:
        task.log.error(
            error=str(exc),
            msg="output parsing error",
        )
        return None
    else:
        return result