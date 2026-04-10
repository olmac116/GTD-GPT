# !/bin/bash

# start docker service if its not already running
systemctl start docker

# remove the old image and build a new one without cache to make sure all changes are included
docker compose -f docker-compose.yml down
# build the new image and start the container
docker compose -f docker-compose.yml up --build