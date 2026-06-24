
# Remove any previous environment
rm -rf nextflow_pipeline/bin/conda-env

# Remove GUI config files so fresh ones can be created
rm config.ini
rm nano_gui/config.ini

# Install the conda environment
conda env create --file nextflow_pipeline/environment.yml --prefix ./nextflow_pipeline/bin/conda-env

