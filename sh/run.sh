# Path for the script root directory
BASEDIR=$(dirname $0)

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
