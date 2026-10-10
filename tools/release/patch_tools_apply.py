"""Apply the English patch to your own copy of the original game.

    python apply.py ORIGINAL [PATCH.bps] [-o OUT.ngc]

ORIGINAL  your copy of the original Japanese game (.ngc/.ngp, or a .zip that
          contains it); it is never changed.
PATCH     the patch; default: ogre_en.bps of the release folder (the folder
          that contains this patch-tools folder), else next to ORIGINAL or
          in the current folder.
-o OUT    where to write the English ROM; default: ogre_en.ngc next to
          ORIGINAL.

The original's SHA-1 is checked before patching, the result's CRC32 and
SHA-1 (ogre_en.sha1 next to the patch) afterwards. Python 3.7 or newer;
nothing to install. The work is done by the modules in the tools folder next
to this file, which are the project's own applier (tools/patch/apply.py) and
BPS decoder (tools/patch/bps.py), unchanged.

(Release package launcher: tools/release/patch_tools_apply.py in the
project's repository, copied here as apply.py by tools/release/package.py.)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)                    # also under python -I
sys.dont_write_bytecode = True                  # leave no __pycache__ in the release folder

from tools.patch import apply as _apply        # noqa: E402

# The default patch is looked up in ROOT first: make that the release folder.
_apply.ROOT = os.path.dirname(HERE)

if __name__ == '__main__':
    sys.exit(_apply.main(prog='python patch-tools/apply.py'))
