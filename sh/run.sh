# Path for the script root directory
BASEDIR=$(dirname $0)

echo "Processing configuration"
echo "ARTICLEMETA_DOMAIN: "$ARTICLEMETA_DOMAIN
echo "ARTICLEMETA_THRIFTSERVER: "$ARTICLEMETA_THRIFTSERVER
echo "HA"

echo "Script running with CISIS version:"
$BASEDIR/../cisis/mx what

mkdir -p $BASEDIR/../databases
mkdir -p $BASEDIR/../isos
mkdir -p $BASEDIR/../tmp
mkdir -p $BASEDIR/../output

colls=`ls -1 $BASEDIR/../isos`
rm -f $BASEDIR/../databases/artigo.*
rm -f $BASEDIR/../databases/title.*
rm -f $BASEDIR/../databases/bib4cit.*
rm -f $BASEDIR/../databases/issue.*

for coll in $colls;
do
   echo "Creating now "$coll" master files"
   $BASEDIR/../cisis/mx iso=$BASEDIR/../isos/$coll/artigo.iso "proc='a992#$coll#'" append=$BASEDIR/../databases/artigo -all now
   $BASEDIR/../cisis/mx iso=$BASEDIR/../isos/$coll/title.iso "proc='a992#$coll#'" append=$BASEDIR/../databases/title -all now
   $BASEDIR/../cisis/mx iso=$BASEDIR/../isos/$coll/bib4cit.iso "proc='a992#$coll#'" append=$BASEDIR/../databases/bib4cit -all now
   $BASEDIR/../cisis/mx iso=$BASEDIR/../isos/$coll/issue.iso "proc='a992#$coll#a880#',v35,v65*0.4,s(f(val(s(v36*4.4))+10000,2,0))*1.4,'#'" append=$BASEDIR/../databases/issue -all now
done

echo "Indexing databases according to FSTs"
$BASEDIR/../cisis/mx $BASEDIR/../databases/artigo  fst="@$BASEDIR/../fst/artigo.fst"  fullinv/ansi=$BASEDIR/../databases/artigo  tell=1000  -all now
$BASEDIR/../cisis/mx $BASEDIR/../databases/title   fst="@$BASEDIR/../fst/title.fst"   fullinv/ansi=$BASEDIR/../databases/title   tell=10    -all now
$BASEDIR/../cisis/mx $BASEDIR/../databases/issue   fst="@$BASEDIR/../fst/issue.fst"   fullinv/ansi=$BASEDIR/../databases/issue   tell=100   -all now
$BASEDIR/../cisis/mx $BASEDIR/../databases/bib4cit fst="@$BASEDIR/../fst/bib4cit.fst" fullinv/ansi=$BASEDIR/../databases/bib4cit tell=10000 -all now

echo "RUNNING UPDATE TITLES"
$BASEDIR/update_titles.sh

echo "RUNNING ADD ISSUES"
$BASEDIR/add_issues.sh

echo "RUNNING UPDATE ISSUES"
$BASEDIR/update_issues.sh

echo "RUNNING DELETE ISSUES"
$BASEDIR/delete_issues.sh

echo "RUNNING ADD ARTICLES"
$BASEDIR/add_articles.sh

echo "RUNNING UPDATE ARTICLES"
$BASEDIR/update_articles.sh

echo "RUNNING DELETE ARTICLES"
$BASEDIR/delete_articles.sh
