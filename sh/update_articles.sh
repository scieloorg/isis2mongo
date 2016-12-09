# Path for the script root directory
BASEDIR=$(dirname $0)

echo "Script running with CISIS version:"
$BASEDIR/../cisis/mx what

mkdir -p $BASEDIR/../databases
mkdir -p $BASEDIR/../isos
mkdir -p $BASEDIR/../tmp
mkdir -p $BASEDIR/../output

echo "Updating Articles"

mkdir -p $BASEDIR/../output/isos/
total_pids=`wc -l $BASEDIR/update_article_identifiers.txt`
from=1
for pid in `cat $BASEDIR/update_article_identifiers.txt`;
do
    collection=${pid:0:3}
    pid=${pid:3:23}
    echo $from"/"$total_pids "-" $pid
    from=$(($from+1))

    mkdir -p $BASEDIR/../output/isos/$pid
    issn=${pid:1:9}
    len=${#pid}
    if [[ $len -eq 23 ]]; then
        $cisis_dir/mx $BASEDIR/../databases/artigo  btell="0" $collection$pid count=1 iso=$BASEDIR/../output/isos/$pid/$pid"_artigo.iso" -all now
        $cisis_dir/mx $BASEDIR/../databases/title   btell="0" $collection$issn count=1 iso=$BASEDIR/../output/isos/$pid/$pid"_title.iso" -all now
        $cisis_dir/mx $BASEDIR/../databases/bib4cit btell="0" $collection$pid"$" iso=$BASEDIR/../output/isos/$pid/$pid"_bib4cit.iso" -all now
        ./isis2json.py $BASEDIR/../output/isos/$pid/$pid"_artigo.iso" -c -p v -t 3 > $BASEDIR/../output/isos/$pid/$pid"_artigo.json"
        ./isis2json.py $BASEDIR/../output/isos/$pid/$pid"_title.iso" -c -p v -t 3 > $BASEDIR/../output/isos/$pid/$pid"_title.json"
        ./isis2json.py $BASEDIR/../output/isos/$pid/$pid"_bib4cit.iso" -c -p v -t 3 > $BASEDIR/../output/isos/$pid/$pid"_bib4cit.json"
        ./packing_json.py 'article' $pid > $BASEDIR/../output/isos/$pid/$pid"_package.json"
        curl -H "Content-Type: application/json" --data @$BASEDIR/../output/isos/$pid/$pid"_package.json" -X POST "http://"$ARTICLEMETA_DOMAIN"/api/v1/article/update/?admintoken="$ARTICLEMETA_ADMINTOKEN
        rm -rf $BASEDIR/../output/isos/$pid
    fi
done

echo '' > $BASEDIR/update_article_identifiers.txt
