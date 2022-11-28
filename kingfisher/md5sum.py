import logging
import hashlib

class MD5:
    @staticmethod
    def check_md5sum(file_path, expected_md5sum):
        logging.debug("Checking md5sum for {} ..".format(file_path))
        
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

        if hash_md5 == expected_md5sum:
            return True
        else:
            return False