class FakeValues:
    def __getattribute__(self, key):
        return self
    def __setattribute__(self, key, value):
        raise TypeError('You cannot set attributes on a Fake object')
    
class DictObject:
    def __init__(self, source):
        self.source = source

    def __getattr__(self, key):
        try:
            value = self.DictObject_source[key]
            if isinstance(value, dict):
                return DictObject(value)
            return value
        except KeyError as e:
            raise AttributeError() from e
        
O = DictObject({'urls': [{'digests': {'md5': 'a37e1f74af580271941f9b25b32d4e3d', 'sha256': '75e889e2e49a76f7387ea935e54c70fd8762fc56860d86a5695f92111a63c335'}, 'downloads': -1, 'filename': 'olefile-0.40.zip', 'has_sig': False, 'md5_digest': 'a37e1f74af580271941f9b25b32d4e3d', 'packagetype': 'sdist', 'python_version': 'source', 'size': 111165, 'upload_time': '2014-10-01T15:26:04', 'upload_time_iso_8601': '2014-10-01T15:26:04.404212Z', 'url': 'https://files.pythonhosted.org/packages/4a/7f/1efe0592a69585eb1c844a816c362877a241f0ed75735314fe33b9d9b653/olefile-0.40.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.40', 'ext': 'zip', 'package_name': 'olefile'}, {'digests': {'md5': 'c183fa8d6d8733d803e416d871bc8ae4', 'sha256': '1f76a5b8ff0e47dbdd22a4f4aa5bc1c29af0bfb3dc12bc86354ae374ad9192f1'}, 'downloads': -1, 'filename': 'olefile-0.41.zip', 'has_sig': False, 'md5_digest': 'c183fa8d6d8733d803e416d871bc8ae4', 'packagetype': 'sdist', 'python_version': 'source', 'size': 117775, 'upload_time': '2014-11-25T21:34:52', 'upload_time_iso_8601': '2014-11-25T21:34:52.499654Z', 'url': 'https://files.pythonhosted.org/packages/ac/a1/f5cf204f1de87c2f59c061075ebc02d702abd415032eece9535126777a48/olefile-0.41.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.41', 'ext': 'zip', 'package_name': 'olefile'}, {'digests': {'md5': '4933a9ba5a5d84647b32e5deb57a4a08', 'sha256': '8a3226dba11349b51a2c6de6af0c889324201f14a8c30992b7877109090e36e0'}, 'downloads': -1, 'filename': 'olefile-0.42.1.zip', 'has_sig': False, 'md5_digest': '4933a9ba5a5d84647b32e5deb57a4a08', 'packagetype': 'sdist', 'python_version': 'source', 'size': 119386, 'upload_time': '2015-01-25T21:20:45', 'upload_time_iso_8601': '2015-01-25T21:20:45.229087Z', 'url': 'https://files.pythonhosted.org/packages/8e/32/db0c062319061c6c38067823485ebc6252423cdc3c1d7dec798ad5c989f4/olefile-0.42.1.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.42.1', 'ext': 'zip', 'package_name': 'olefile'}, {'digests': {'md5': 'f570df81ebfab51aaa538af39fef6fd3', 'sha256': '57102bf3f19c5fa099c0c7128190fe4bb28cd2760aa08f4b5b7dccf28718b876'}, 'downloads': -1, 'filename': 'olefile-0.43.tar.gz', 'has_sig': False, 'md5_digest': 'f570df81ebfab51aaa538af39fef6fd3', 'packagetype': 'sdist', 'python_version': 'source', 'size': 99723, 'upload_time': '2016-02-03T20:05:10', 'upload_time_iso_8601': '2016-02-03T20:05:10.159442Z', 'url': 'https://files.pythonhosted.org/packages/61/f4/7b52981ee0c3c2521c504fa318466136be8d47bc720ef1eff2aa2f193730/olefile-0.43.tar.gz', 'yanked': False, 'distribution': 'olefile', 'version': '0.43', 'ext': '.tar.gz', 'package_name': 'olefile'}, {'digests': {'md5': '99700591a76c9845889170f4bb9fbfa3', 'sha256': '7bc605bc2ebd3475eaf91513b5b5e10e0992312cff994a38145cd8e3585766f5'}, 'downloads': -1, 'filename': 'olefile-0.43.zip', 'has_sig': False, 'md5_digest': '99700591a76c9845889170f4bb9fbfa3', 'packagetype': 'sdist', 'python_version': 'source', 'size': 119525, 'upload_time': '2016-02-03T20:05:30', 'upload_time_iso_8601': '2016-02-03T20:05:30.390654Z', 'url': 'https://files.pythonhosted.org/packages/61/c5/3fde261fc03c6cc80a591b505657698976c7bc962c0fcf92ba6b667cfb2e/olefile-0.43.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.43', 'ext': 'zip', 'package_name': 'olefile'}, {'digests': {'md5': 'fc625554e4e7f0c2ddcd00baa3c74ff5', 'sha256': '61f2ca0cd0aa77279eb943c07f607438edf374096b66332fae1ee64a6f0f73ad'}, 'downloads': -1, 'filename': 'olefile-0.44.zip', 'has_sig': False, 'md5_digest': 'fc625554e4e7f0c2ddcd00baa3c74ff5', 'packagetype': 'sdist', 'python_version': 'source', 'size': 74147, 'upload_time': '2017-01-06T16:37:23', 'upload_time_iso_8601': '2017-01-06T16:37:23.759771Z', 'url': 'https://files.pythonhosted.org/packages/35/17/c15d41d5a8f8b98cc3df25eb00c5cee76193114c78e5674df6ef4ac92647/olefile-0.44.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.44', 'ext': 'zip', 'package_name': 'olefile'}, {'digests': {'md5': '0296cebeb4e3933b2e002d8eac0279a5', 'sha256': '8009f50bdaafc2247546d3105be61e0bb38d21098b36dd5fc9eed05be28bba7b'}, 'downloads': -1, 'filename': 'olefile-0.45.zip', 'has_sig': False, 'md5_digest': '0296cebeb4e3933b2e002d8eac0279a5', 'packagetype': 'sdist', 'python_version': 'source', 'requires_python': '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*', 'size': 111920, 'upload_time': '2018-01-24T22:40:38', 'upload_time_iso_8601': '2018-01-24T22:40:38.177799Z', 'url': 'https://files.pythonhosted.org/packages/10/1b/a38e82a67ed1e67d112e8a5e664b12c669263d51929f6b15ba41fa225067/olefile-0.45.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.45', 'ext': 'zip', 'package_name': 'olefile'}, {'digests': {'md5': 'f70c0688320548ae0f1b4785e7aefcb9', 'sha256': '2b6575f5290de8ab1086f8c5490591f7e0885af682c7c1793bdaf6e64078d385'}, 'downloads': -1, 'filename': 'olefile-0.45.1.zip', 'has_sig': False, 'md5_digest': 'f70c0688320548ae0f1b4785e7aefcb9', 'packagetype': 'sdist', 'python_version': 'source', 'requires_python': '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*', 'size': 112359, 'upload_time': '2018-01-25T10:22:22', 'upload_time_iso_8601': '2018-01-25T10:22:22.965019Z', 'url': 'https://files.pythonhosted.org/packages/d3/8a/e0f0e56d6a542dd987f9290ef7b5164636ee597ce8c2932c19c78292d5ec/olefile-0.45.1.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.45.1', 'ext': 'zip', 'package_name': 'olefile'}, {'digests': {'md5': 'af351575e53aa00c36ae1c71ee9b0043', 'sha256': '133b031eaf8fd2c9399b78b8bc5b8fcbe4c31e85295749bb17a87cba8f3c3964'}, 'downloads': -1, 'filename': 'olefile-0.46.zip', 'has_sig': False, 'md5_digest': 'af351575e53aa00c36ae1c71ee9b0043', 'packagetype': 'sdist', 'python_version': 'source', 'requires_python': '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*', 'size': 112226, 'upload_time': '2018-09-10T18:35:52', 'upload_time_iso_8601': '2018-09-10T18:35:52.289073Z', 'url': 'https://files.pythonhosted.org/packages/34/81/e1ac43c6b45b4c5f8d9352396a14144bba52c8fec72a80f425f6a4d653ad/olefile-0.46.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.46', 'ext': 'zip', 'package_name': 'olefile'}, {'digests': {'md5': 'd0474cf211fb1df5e8c53c797f7d87e4', 'sha256': '44c94689f81b216be09c475172ff01121c66d6ee8679f957903c1eb47e93b3dd'}, 'downloads': -1, 'filename': 'olefile-0.47.dev4-py2.py3-none-any.whl', 'has_sig': False, 'md5_digest': 'd0474cf211fb1df5e8c53c797f7d87e4', 'packagetype': 'bdist_wheel', 'python_version': 'py2.py3', 'requires_python': '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*', 'size': 114893, 'upload_time': '2020-11-03T21:26:11', 'upload_time_iso_8601': '2020-11-03T21:26:11.909507Z', 'url': 'https://files.pythonhosted.org/packages/73/fb/f1e3ce82277c9e460e687f85e5d3049aa90dc527df4b8e0b9b9378824ef8/olefile-0.47.dev4-py2.py3-none-any.whl', 'yanked': False, 'distribution': 'olefile', 'version': '0.47.dev4', 'python_tag': 'py2.py3', 'abi_tag': 'none', 'platform_tag': 'any', 'ext': 'whl', 'package_name': 'olefile'}, {'digests': {'md5': '37bfa5f1be94bbdeee67022438b4c035', 'sha256': 'aeeee946f56559f902a2478530aa1dbef892fc983956a7f2db16f48b619a2809'}, 'downloads': -1, 'filename': 'olefile-0.47.dev4.zip', 'has_sig': False, 'md5_digest': '37bfa5f1be94bbdeee67022438b4c035', 'packagetype': 'sdist', 'python_version': 'source', 'requires_python': '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*', 'size': 109839, 'upload_time': '2020-11-03T21:26:14', 'upload_time_iso_8601': '2020-11-03T21:26:14.753248Z', 'url': 'https://files.pythonhosted.org/packages/ff/47/a56c2812bc96dd4e33aba3acac0e2d9c78d9ef768d6654a84a343647c7f1/olefile-0.47.dev4.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.47.dev4', 'ext': 'zip', 'package_name': 'olefile'}], 'releases': {'0.40': [{'digests': {'md5': 'a37e1f74af580271941f9b25b32d4e3d', 'sha256': '75e889e2e49a76f7387ea935e54c70fd8762fc56860d86a5695f92111a63c335'}, 'downloads': -1, 'filename': 'olefile-0.40.zip', 'has_sig': False, 'md5_digest': 'a37e1f74af580271941f9b25b32d4e3d', 'packagetype': 'sdist', 'python_version': 'source', 'size': 111165, 'upload_time': '2014-10-01T15:26:04', 'upload_time_iso_8601': '2014-10-01T15:26:04.404212Z', 'url': 'https://files.pythonhosted.org/packages/4a/7f/1efe0592a69585eb1c844a816c362877a241f0ed75735314fe33b9d9b653/olefile-0.40.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.40', 'ext': 'zip', 'package_name': 'olefile'}], '0.41': [{'digests': {'md5': 'c183fa8d6d8733d803e416d871bc8ae4', 'sha256': '1f76a5b8ff0e47dbdd22a4f4aa5bc1c29af0bfb3dc12bc86354ae374ad9192f1'}, 'downloads': -1, 'filename': 'olefile-0.41.zip', 'has_sig': False, 'md5_digest': 'c183fa8d6d8733d803e416d871bc8ae4', 'packagetype': 'sdist', 'python_version': 'source', 'size': 117775, 'upload_time': '2014-11-25T21:34:52', 'upload_time_iso_8601': '2014-11-25T21:34:52.499654Z', 'url': 'https://files.pythonhosted.org/packages/ac/a1/f5cf204f1de87c2f59c061075ebc02d702abd415032eece9535126777a48/olefile-0.41.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.41', 'ext': 'zip', 'package_name': 'olefile'}], '0.42.1': [{'digests': {'md5': '4933a9ba5a5d84647b32e5deb57a4a08', 'sha256': '8a3226dba11349b51a2c6de6af0c889324201f14a8c30992b7877109090e36e0'}, 'downloads': -1, 'filename': 'olefile-0.42.1.zip', 'has_sig': False, 'md5_digest': '4933a9ba5a5d84647b32e5deb57a4a08', 'packagetype': 'sdist', 'python_version': 'source', 'size': 119386, 'upload_time': '2015-01-25T21:20:45', 'upload_time_iso_8601': '2015-01-25T21:20:45.229087Z', 'url': 'https://files.pythonhosted.org/packages/8e/32/db0c062319061c6c38067823485ebc6252423cdc3c1d7dec798ad5c989f4/olefile-0.42.1.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.42.1', 'ext': 'zip', 'package_name': 'olefile'}], '0.43': [{'digests': {'md5': 'f570df81ebfab51aaa538af39fef6fd3', 'sha256': '57102bf3f19c5fa099c0c7128190fe4bb28cd2760aa08f4b5b7dccf28718b876'}, 'downloads': -1, 'filename': 'olefile-0.43.tar.gz', 'has_sig': False, 'md5_digest': 'f570df81ebfab51aaa538af39fef6fd3', 'packagetype': 'sdist', 'python_version': 'source', 'size': 99723, 'upload_time': '2016-02-03T20:05:10', 'upload_time_iso_8601': '2016-02-03T20:05:10.159442Z', 'url': 'https://files.pythonhosted.org/packages/61/f4/7b52981ee0c3c2521c504fa318466136be8d47bc720ef1eff2aa2f193730/olefile-0.43.tar.gz', 'yanked': False, 'distribution': 'olefile', 'version': '0.43', 'ext': '.tar.gz', 'package_name': 'olefile'}, {'digests': {'md5': '99700591a76c9845889170f4bb9fbfa3', 'sha256': '7bc605bc2ebd3475eaf91513b5b5e10e0992312cff994a38145cd8e3585766f5'}, 'downloads': -1, 'filename': 'olefile-0.43.zip', 'has_sig': False, 'md5_digest': '99700591a76c9845889170f4bb9fbfa3', 'packagetype': 'sdist', 'python_version': 'source', 'size': 119525, 'upload_time': '2016-02-03T20:05:30', 'upload_time_iso_8601': '2016-02-03T20:05:30.390654Z', 'url': 'https://files.pythonhosted.org/packages/61/c5/3fde261fc03c6cc80a591b505657698976c7bc962c0fcf92ba6b667cfb2e/olefile-0.43.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.43', 'ext': 'zip', 'package_name': 'olefile'}], '0.44': [{'digests': {'md5': 'fc625554e4e7f0c2ddcd00baa3c74ff5', 'sha256': '61f2ca0cd0aa77279eb943c07f607438edf374096b66332fae1ee64a6f0f73ad'}, 'downloads': -1, 'filename': 'olefile-0.44.zip', 'has_sig': False, 'md5_digest': 'fc625554e4e7f0c2ddcd00baa3c74ff5', 'packagetype': 'sdist', 'python_version': 'source', 'size': 74147, 'upload_time': '2017-01-06T16:37:23', 'upload_time_iso_8601': '2017-01-06T16:37:23.759771Z', 'url': 'https://files.pythonhosted.org/packages/35/17/c15d41d5a8f8b98cc3df25eb00c5cee76193114c78e5674df6ef4ac92647/olefile-0.44.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.44', 'ext': 'zip', 'package_name': 'olefile'}], '0.45': [{'digests': {'md5': '0296cebeb4e3933b2e002d8eac0279a5', 'sha256': '8009f50bdaafc2247546d3105be61e0bb38d21098b36dd5fc9eed05be28bba7b'}, 'downloads': -1, 'filename': 'olefile-0.45.zip', 'has_sig': False, 'md5_digest': '0296cebeb4e3933b2e002d8eac0279a5', 'packagetype': 'sdist', 'python_version': 'source', 'requires_python': '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*', 'size': 111920, 'upload_time': '2018-01-24T22:40:38', 'upload_time_iso_8601': '2018-01-24T22:40:38.177799Z', 'url': 'https://files.pythonhosted.org/packages/10/1b/a38e82a67ed1e67d112e8a5e664b12c669263d51929f6b15ba41fa225067/olefile-0.45.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.45', 'ext': 'zip', 'package_name': 'olefile'}], '0.45.1': [{'digests': {'md5': 'f70c0688320548ae0f1b4785e7aefcb9', 'sha256': '2b6575f5290de8ab1086f8c5490591f7e0885af682c7c1793bdaf6e64078d385'}, 'downloads': -1, 'filename': 'olefile-0.45.1.zip', 'has_sig': False, 'md5_digest': 'f70c0688320548ae0f1b4785e7aefcb9', 'packagetype': 'sdist', 'python_version': 'source', 'requires_python': '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*', 'size': 112359, 'upload_time': '2018-01-25T10:22:22', 'upload_time_iso_8601': '2018-01-25T10:22:22.965019Z', 'url': 'https://files.pythonhosted.org/packages/d3/8a/e0f0e56d6a542dd987f9290ef7b5164636ee597ce8c2932c19c78292d5ec/olefile-0.45.1.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.45.1', 'ext': 'zip', 'package_name': 'olefile'}], '0.46': [{'digests': {'md5': 'af351575e53aa00c36ae1c71ee9b0043', 'sha256': '133b031eaf8fd2c9399b78b8bc5b8fcbe4c31e85295749bb17a87cba8f3c3964'}, 'downloads': -1, 'filename': 'olefile-0.46.zip', 'has_sig': False, 'md5_digest': 'af351575e53aa00c36ae1c71ee9b0043', 'packagetype': 'sdist', 'python_version': 'source', 'requires_python': '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*', 'size': 112226, 'upload_time': '2018-09-10T18:35:52', 'upload_time_iso_8601': '2018-09-10T18:35:52.289073Z', 'url': 'https://files.pythonhosted.org/packages/34/81/e1ac43c6b45b4c5f8d9352396a14144bba52c8fec72a80f425f6a4d653ad/olefile-0.46.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.46', 'ext': 'zip', 'package_name': 'olefile'}], '0.47.dev4': [{'digests': {'md5': 'd0474cf211fb1df5e8c53c797f7d87e4', 'sha256': '44c94689f81b216be09c475172ff01121c66d6ee8679f957903c1eb47e93b3dd'}, 'downloads': -1, 'filename': 'olefile-0.47.dev4-py2.py3-none-any.whl', 'has_sig': False, 'md5_digest': 'd0474cf211fb1df5e8c53c797f7d87e4', 'packagetype': 'bdist_wheel', 'python_version': 'py2.py3', 'requires_python': '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*', 'size': 114893, 'upload_time': '2020-11-03T21:26:11', 'upload_time_iso_8601': '2020-11-03T21:26:11.909507Z', 'url': 'https://files.pythonhosted.org/packages/73/fb/f1e3ce82277c9e460e687f85e5d3049aa90dc527df4b8e0b9b9378824ef8/olefile-0.47.dev4-py2.py3-none-any.whl', 'yanked': False, 'distribution': 'olefile', 'version': '0.47.dev4', 'python_tag': 'py2.py3', 'abi_tag': 'none', 'platform_tag': 'any', 'ext': 'whl', 'package_name': 'olefile'}, {'digests': {'md5': '37bfa5f1be94bbdeee67022438b4c035', 'sha256': 'aeeee946f56559f902a2478530aa1dbef892fc983956a7f2db16f48b619a2809'}, 'downloads': -1, 'filename': 'olefile-0.47.dev4.zip', 'has_sig': False, 'md5_digest': '37bfa5f1be94bbdeee67022438b4c035', 'packagetype': 'sdist', 'python_version': 'source', 'requires_python': '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*', 'size': 109839, 'upload_time': '2020-11-03T21:26:14', 'upload_time_iso_8601': '2020-11-03T21:26:14.753248Z', 'url': 'https://files.pythonhosted.org/packages/ff/47/a56c2812bc96dd4e33aba3acac0e2d9c78d9ef768d6654a84a343647c7f1/olefile-0.47.dev4.zip', 'yanked': False, 'distribution': 'olefile', 'version': '0.47.dev4', 'ext': 'zip', 'package_name': 'olefile'}]}})