processing_path="/bases/isis2mongo"

cd $processing_path

. $processing_path/sh/config.sh

echo "Script running with CISIS version:"
$cisis_dir/mx what

mkdir -p $processing_path/databases
mkdir -p $processing_path/iso
mkdir -p $processing_path/tmp
mkdir -p $processing_path/output

echo "Removing exceded files from Article Meta"

tot_to_remove=`cat $processing_path/sh/to_remove_article_identifiers.txt | wc -l`

if (($tot_to_remove < 2000)); then
    for pid in `cat $processing_path/sh/to_remove_article_identifiers.txt`;
    do
      collection=${pid:0:3}
      pid=${pid:3:23}
      durl="http://"$scielo_data_url"/api/v1/article/delete/?code="$pid"&collection="$collection"&admintoken="$admintoken
      curl -X DELETE $durl
    done
else
  echo "To many files to remove. I will not remove then, please check it before"
fi
