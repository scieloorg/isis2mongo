# Path for the script root directory
BASEDIR=$(dirname $0)

echo "Script running with CISIS version:"
$BASEDIR/../cisis/mx what

mkdir -p $BASEDIR/../databases
mkdir -p $BASEDIR/../isos
mkdir -p $BASEDIR/../tmp
mkdir -p $BASEDIR/../output

echo "Removing exceded issues files from Article Meta"

tot_to_remove=`cat $BASEDIR/to_remove_issue_identifiers.txt | wc -l`

if (($tot_to_remove < 2000)); then
    for pid in `cat $BASEDIR/to_remove_issue_identifiers.txt`;
    do
      collection=${pid:0:3}
      pid=${pid:3:17}
      durl="http://"$ARTICLEMETA_DOMAIN"/api/v1/issue/delete/?code="$pid"&collection="$collection"&admintoken="$ARTICLEMETA_ADMINTOKEN
      curl -X DELETE $durl
    done
else
  echo "To many files to remove. I will not remove then, please check it before"
fi
