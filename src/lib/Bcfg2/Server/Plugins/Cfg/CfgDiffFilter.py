""" Handle .diff files, which apply diffs to plaintext files """

import hashlib
import os
import tempfile
from Bcfg2.Server.Plugin import PluginExecutionError
from subprocess import Popen, PIPE
from Bcfg2.Server.Plugins.Cfg import CfgFilter


class CfgDiffFilter(CfgFilter):
    """ CfgDiffFilter applies diffs to plaintext
    :ref:`server-plugins-generators-Cfg` files """

    #: Handle .diff files
    __extensions__ = ['diff']

    #: .diff files are deprecated
    deprecated = True

    def modify_data(self, entry, metadata, data):

        # Use a cache for patch, based on file checksum

        dirCache = "/var/cache/bcfg2-server/diffFilter/"

        dataChecksum = hashlib.md5(data).hexdigest()
        patchChecksum = hashlib.md5(self.data).hexdigest()

        cacheName = dataChecksum +"-"+ patchChecksum

        cacheFile = dirCache + cacheName

        # If cache exists, then use it
        if os.path.exists(cacheFile):
            return open(cacheFile).read()

        # We need to work on a temporary file
        tmpFile = dirCache +"."+ cacheName +"."+ str(os.getpid())

        # Create file to patch
        fileHandle = open(tmpFile, "w")
        fileHandle.write(data)
        fileHandle.close()

        # Path the file
        cmd = ["patch", "-u", "-f", tmpFile]
        patch = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stderr = patch.communicate(input=self.data)[1]
        ret = patch.wait()

        if ret != 0:
            os.unlink(tmpFile)
            raise PluginExecutionError("Error applying diff %s: %s" %
                                       (self.name, stderr))

        # Keep result as cache
        os.rename(tmpFile, cacheFile)

        output = open(cacheFile).read()

        return output
    modify_data.__doc__ = CfgFilter.modify_data.__doc__
