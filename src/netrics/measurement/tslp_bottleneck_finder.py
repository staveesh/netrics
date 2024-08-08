"""Detect a bottlenecked link along the speedtest path for Ookla or NDT7."""
import json
import subprocess

from schema import Optional, Or

from netrics import task

from .common import require_net


PARAMS = task.schema.extend('tslp-bottleneck-finder', {
    # exec: ndt7-client executable name or path
    Optional('exec', default='tslp-bottleneck-finder'): task.schema.Command(
        error='exec: must be an executable on PATH or file system absolute path to executable'
    ),

    # count: Number of packets to capture before stopping (default 10)
    Optional('count', default='10'): task.schema.NaturalStr('count'),

    # maxTTL: Maximum TTL to send ping commands to (default 5)
    Optional('maxTTL', default='5'): task.schema.NaturalStr('maxTTL'),

    # pingType: Type of ping to use (default 'icmp')
    Optional('pingType', default='icmp'): Or(str, error='pingType: string'),

    # toolType: Type of tool to use (default 'ndt')
    Optional('toolType', default='ndt'): Or(str, error='toolType: string'),

    # timeout: seconds after which test is canceled
    # (0, None, False, etc. to disable timeout)
    Optional('timeout', default=45): Or(task.schema.GTZero(),
                                        task.schema.falsey,
                                        error='timeout: seconds greater than zero or '
                                              'falsey to disable'),
})


def parse_output():
    """
    Parse the output of the tslp-bottleneck-finder binary.
    """
    pass

@task.param.require(PARAMS)
@require_net
def main(params):
    """
    Locate the bottlenecked link along the path of an NDT7/Ookla speedtest.

    The local network, and then Internet hosts (as configured in global
    defaults), are queried first, to ensure network operation and
    internet accessibility. (See: `require_net`.)

    The tslp-bottleneck-finder binary is then executed.

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
                '-c', params.count,
                '-d', 'data', # A temporary directory to write outputs to; will be created if it doesn't exist. Deleted after the test finishes.
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

    results = {"Status": "Success"}
    task.result.write(results,
                label=params.result.label,
                annotate=params.result.annotate,
                extend=None)

    return task.status.success