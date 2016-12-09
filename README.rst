isis2mongo
==========

Ferramenta para exportar registros de bases de dados SciELO em ISIS para o MongoDB.

    Para histórico de desenvolvimento anterior ao registrado neste repositório, verificar: https://bitbucket.org/scieloorg/xmlwos


Como executar
=============

docker run --rm --name isis2mongo -v PATH_ISOS:/app/isos -e ARTICLEMETA_DOMAIN=articlemeta.scielo.org -e ARTICLEMETA_THRIFTSERVER=articlemeta.scielo.org:11620 -e ARTICLEMETA_ADMINTOKEN=admin isis2mongo