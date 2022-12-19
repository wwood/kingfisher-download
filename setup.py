import io
from os.path import dirname, join
from setuptools import setup


# read the contents of your README file
from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


def get_version(relpath):
  """Read version info from a file without importing it"""
  for line in io.open(join(dirname(__file__), relpath), encoding="cp437"):
    if "__version__" in line:
      if '"' in line:
        return line.split('"')[1]
      elif "'" in line:
        return line.split("'")[1]


setup(
    name='kingfisher',
    version=get_version("kingfisher/version.py"),
    url='https://github.com/wwood/kingfisher-download',
    license='GPL3+',
    author='Ben Woodcroft',
    author_email='benjwoodcroft@gmail.com',
    description='Download/extract biological FASTA/Q read data and metadata',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=['kingfisher'],
    package_data={'kingfisher': [
            'data/asperaweb_id_dsa.openssh',
                       ]},
    data_files=[(".", ["README.md", "LICENCE.txt"])],
    include_package_data=True,
    install_requires= [
      'extern',
      'requests',
      'tqdm',
      'pandas',
      'bird_tool_utils',
      'pyarrow',
    ],
    scripts=['bin/kingfisher'],
    classifiers=["Topic :: Scientific/Engineering :: Bio-Informatics"],
)
