# Path for the script root directory
BASEDIR=$(dirname $0)

echo "Script running with CISIS version:"
$BASEDIR/../cisis/mx what

mkdir -p $BASEDIR/../databases
mkdir -p $BASEDIR/../isos
mkdir -p $BASEDIR/../tmp
mkdir -p $BASEDIR/../output

echo "Updating title database"

$BASEDIR/../cisis/mx $BASEDIR/../databases/title "pft=v992,v400,/" -all now > $BASEDIR/issns.txt

itens=`cat $BASEDIR/issns.txt`
for issn in $itens; do
   echo "Updating: "$issn
   collection=${issn:0:3}
   issn=${issn:3:9}
   mkdir -p $BASEDIR/../output/isos/$issn
   $BASEDIR/../cisis/mx $BASEDIR/../databases/title btell="0" $collection$issn iso=$BASEDIR/../output/isos/$issn/$issn"_title.iso" -all now
   ./isis2json.py $BASEDIR/../output/isos/$issn/$issn"_title.iso" -c -p v -t 3 > $BASEDIR/../output/isos/$issn/$issn"_title.json"
   ./packing_json.py 'journal' $issn > $BASEDIR/../output/isos/$issn/$issn"_package.json"
   curl -H "Content-Type: application/json" --data @$BASEDIR/../output/isos/$issn/$issn"_package.json" -X POST "http://"$ARTICLEMETA_DOMAIN"/api/v1/journal/add/?admintoken="$ARTICLEMETA_ADMINTOKEN
   rm -rf $BASEDIR/../output/isos/$issn
done

rm $BASEDIR/issns.txt
