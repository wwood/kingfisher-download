
#!/bin/bash -eo pipefail

export KINGFISHER_VERSION=`../bin/kingfisher --version`
export KINGFISHER_DOCKER_VERSION=wwood/kingfisher:$KINGFISHER_VERSION

cp ../kingfisher.yml . && \
sed 's/KINGFISHER_VERSION/'$KINGFISHER_VERSION'/g' Dockerfile.in > Dockerfile && \
DOCKER_BUILDKIT=1 docker build -t $KINGFISHER_DOCKER_VERSION . && \
rm -rf SRR12118866* && \
docker run -v `pwd`:`pwd` $KINGFISHER_DOCKER_VERSION get -r SRR12118866 -m ena-ftp --output-format-possibilities fasta.gz && \
echo "Seems good - now you just need to 'docker push $KINGFISHER_DOCKER_VERSION'"
