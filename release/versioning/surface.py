#!/usr/bin/env python3
"""Public surface of the npm distribution declared by ./package.json.

Prints {"surface": ["name", ...]} on stdout.

WHY THIS SET IS THE CONTRACT
----------------------------
What a consumer of this package holds after `npm install wisent` is what it can
import and what it can run:

  * `export:<name>` -- every name reachable from the package entry point, which is
    whatever `exports`/`types`/`main` points at.  An import that resolved
    yesterday must resolve today.  The default export is `export:default`, because
    the identifier the declaration happens to use is not a name any consumer
    spells.
  * `member:<Exported>.<path>` -- the public members of every exported class,
    interface, type alias and enum.  A name-only surface would call
    `WisentClient.getApiKey` internal and let it be deleted without notice; the
    exported name set never moves while the whole class empties out.  Members of
    nested object types carry a dotted path (`InferenceResponse.usage.totalTokens`)
    because a consumer reads them the same way.
  * `bin:<command>` -- every command in the `bin` map.  A rename there breaks a
    script that ran yesterday.  This distribution declares no `bin` today; the
    reader emits the names anyway so adding one registers as additive rather than
    as nothing at all.

Excluded, deliberately: `private`/`protected` members, `#`-private and
`_`-prefixed ones, and `constructor` -- none of which a consumer selects by name;
and every module not reachable from the entry point, which npm ships as a file but
nobody can import by name.

WHY IT IS READ STATICALLY
-------------------------
The same reader must run against an unpacked published tarball (`dist/*.d.ts`) and
against a working tree (`src/*.ts`), because that is how a baseline is recovered
rather than assumed.  Running `tsc` or importing the package would make the
recovered surface a property of the runner's toolchain and network instead of a
property of the artifact.  Declaration files and sources are read by one scanner:
`export declare class C { m(): void; }` and `export class C { m(): void {} }` yield
the same names.

WHY IT FAILS LOUDLY
-------------------
A module that does not parse, a relative import that does not resolve, or an
unbalanced bracket is a hard error.  Skipping one reports a *shorter* surface, and
the rule reads a shorter surface as removed capability -- a breaking verdict for a
change nobody made.  `--tolerant` exists only for recovering an artifact that is
already published, and it names every module it skipped on stderr.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from surface_reader.distribution import compute
from surface_reader.lexer import ONE, TWO, ZERO, SurfaceError

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[ZERO])
    parser.add_argument("--root", default=".", help="directory holding package.json")
    parser.add_argument("--tolerant", action="store_true",
                        help="skip unreadable non-entry modules and name them on stderr; "
                             "for recovering an already-published artifact only")
    args = parser.parse_args(argv)
    try:
        surface = compute(Path(args.root).resolve(), args.tolerant)
    except SurfaceError as error:
        print("surface: " + str(error), file=sys.stderr)
        return ONE
    except (json.JSONDecodeError, OSError) as error:
        print("surface: " + str(error), file=sys.stderr)
        return ONE
    json.dump({"surface": surface}, sys.stdout, indent=TWO)
    sys.stdout.write("\n")
    return ZERO


if __name__ == "__main__":
    raise SystemExit(main())
