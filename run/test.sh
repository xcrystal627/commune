
PWD=$(pwd) ;  
REPO=$(basename $PWD)
NAME=$REPO-test
./run/stop.sh $NAME
docker run -d --name $NAME -v $PWD:/$REPO $REPO
docker exec -it $NAME pytest /$REPO/tests
./run/stop.sh $NAME
