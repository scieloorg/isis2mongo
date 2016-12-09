# Path for the script root directory
BASEDIR=$(dirname $0)

echo "Script running with CISIS version:"
$BASEDIR/../cisis/mx what

mkdir -p $BASEDIR/../databases
mkdir -p $BASEDIR/../isos
mkdir -p $BASEDIR/../tmp
mkdir -p $BASEDIR/../output

echo "Listing legacy articles identifiers"
$BASEDIR/../cisis/mx $BASEDIR/../databases/artigo "pft=if p(v880) then,v992,v880,v91, fi,/" -all now > $BASEDIR/legacy_article_identifiers.txt

echo "Listing articlemeta articles identifiers"
./loading_article_ids.py

echo "Adding Articles"

echo "Creating json files for each new article"
mkdir -p $BASEDIR/../output/isos/
total_pids=`wc -l $BASEDIR/new_article_identifiers.txt`
from=1
for pid in `cat $BASEDIR/new_article_identifiers.txt`;
do
    collection=${pid:0:3}
    pid=${pid:3:23}
    echo $from"/"$total_pids "-" $pid
    from=$(($from+1))

    loaded=`curl -s -X GET "http://"$ARTICLEMETA_DOMAIN"/api/v1/article/exists/?code=$pid&collection=$collection"`
    if [[ $loaded == "false" ]]; then
        mkdir -p $BASEDIR/../output/isos/$pid
        issn=${pid:1:9}
        len=${#pid}
        if [[ $len -eq 23 ]]; then
            $BASEDIR/../cisis/mx $BASEDIR/../databases/artigo  btell="0" $collection$pid count=1 iso=$BASEDIR/../output/isos/$pid/$pid"_artigo.iso" -all now
            $BASEDIR/../cisis/mx $BASEDIR/../databases/title   btell="0" $collection$issn count=1 iso=$BASEDIR/../output/isos/$pid/$pid"_title.iso" -all now
            $BASEDIR/../cisis/mx $BASEDIR/../databases/bib4cit btell="0" $collection$pid"$" iso=$BASEDIR/../output/isos/$pid/$pid"_bib4cit.iso" -all now
            ./isis2json.py $BASEDIR/../output/isos/$pid/$pid"_artigo.iso" -c -p v -t 3 > $BASEDIR/../output/isos/$pid/$pid"_artigo.json"
            ./isis2json.py $BASEDIR/../output/isos/$pid/$pid"_title.iso" -c -p v -t 3 > $BASEDIR/../output/isos/$pid/$pid"_title.json"
            ./isis2json.py $BASEDIR/../output/isos/$pid/$pid"_bib4cit.iso" -c -p v -t 3 > $BASEDIR/../output/isos/$pid/$pid"_bib4cit.json"
            ./packing_json.py 'article' $pid > $BASEDIR/../output/isos/$pid/$pid"_package.json"
            curl -H "Content-Type: application/json" --data @$BASEDIR/../output/isos/$pid/$pid"_package.json" -X POST "http://"$ARTICLEMETA_DOMAIN"/api/v1/article/add/?admintoken="$ARTICLEMETA_ADMINTOKEN
            rm -rf $processing_path/output/isos/$pid
        fi
    else
        echo "article alread processed!!!"
        echo $collection$pid >> $BASEDIR/update_article_identifiers.txt
    fi
done
