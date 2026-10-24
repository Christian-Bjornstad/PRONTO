"""Direct CNV column aliases for display; original source tables remain intact."""


def cnv_display_fields(fields):
    result = dict(fields)
    for label, source in (('Gene_Symbol', 'gene.name'), ('Chromosome', 'chr'), ('Tumor_CN', 'total.cn')):
        if label not in result and source in result:
            result[label] = result[source]
    return result
