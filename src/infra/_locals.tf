# _locals.tf

# Naming variables for AI Foundry resources
locals {
  resource_group_name    = "rg-${local.resource_long_name}"
  cognitive_account_name = "cogacct-${local.resource_long_name}"
  cognitive_project_name = "proj-${local.resource_simple_name}"
  acr_name               = "cr${local.resource_alphanum_name}"
}

/*
  Build a clean tags map — merge base tags with non-empty optional tags,
  matching Bicep's union() pattern that omits keys with null values.
*/
locals {
  tags = merge(
    var.tags,
    var.owner != "" ? { owner = var.owner } : {},
    var.cost_center != "" ? { costCenter = var.cost_center } : {},
    var.business_unit != "" ? { businessUnit = var.business_unit } : {},
    var.criticality != "" ? { criticality = var.criticality } : {},
    var.data_classification != "" ? { dataClassification = var.data_classification } : {},
    var.expiry_date != "" ? { expiryDate = var.expiry_date } : {},
  )
}
