resource "azurerm_resource_group" "app" {
  name     = "rg-vigia-chuva"
  location = var.localizacao
  tags     = local.tags
}

resource "azurerm_virtual_network" "app" {
  name                = "vnet-vigia"
  location            = var.localizacao
  resource_group_name = azurerm_resource_group.app.name
  address_space       = ["10.20.0.0/16"]
  tags                = local.tags
}
resource "azurerm_subnet" "app" {
  name                 = "snet-app"
  resource_group_name  = azurerm_resource_group.app.name
  virtual_network_name = azurerm_virtual_network.app.name
  address_prefixes     = ["10.20.1.0/24"]
  service_endpoints    = ["Microsoft.KeyVault"]
}
resource "azurerm_network_security_group" "app" {
  name                = "nsg-vigia"
  location            = var.localizacao
  resource_group_name = azurerm_resource_group.app.name
  tags                = local.tags
}
# Entrada HTTP publica necessaria para redirecionamento ao HTTPS e validacao ACME.
#trivy:ignore:AVD-AZU-0047
resource "azurerm_network_security_rule" "http" {
  name                        = "permitir-http"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "80"
  source_address_prefix       = "Internet"
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.app.name
  network_security_group_name = azurerm_network_security_group.app.name
}
# HTTPS publico e a entrada de trafego do MVP.
#trivy:ignore:AVD-AZU-0047
resource "azurerm_network_security_rule" "https" {
  name                        = "permitir-https"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = "Internet"
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.app.name
  network_security_group_name = azurerm_network_security_group.app.name
}
resource "azurerm_network_security_rule" "ssh" {
  count                       = var.admin_cidr == null ? 0 : 1
  name                        = "permitir-ssh-admin"
  priority                    = 120
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "22"
  source_address_prefix       = var.admin_cidr
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.app.name
  network_security_group_name = azurerm_network_security_group.app.name
}
resource "azurerm_subnet_network_security_group_association" "app" {
  subnet_id                 = azurerm_subnet.app.id
  network_security_group_id = azurerm_network_security_group.app.id
}
resource "azurerm_public_ip" "app" {
  name                = "pip-vigia"
  location            = var.localizacao
  resource_group_name = azurerm_resource_group.app.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "vigia-chuva-${random_string.sufixo.result}"
  tags                = local.tags
}
resource "azurerm_network_interface" "app" {
  name                = "nic-vigia"
  location            = var.localizacao
  resource_group_name = azurerm_resource_group.app.name
  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.app.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.app.id
  }
  tags = local.tags
}
resource "azurerm_linux_virtual_machine" "app" {
  name                            = "vm-vigia-chuva"
  location                        = var.localizacao
  resource_group_name             = azurerm_resource_group.app.name
  size                            = var.tamanho_vm
  admin_username                  = "vigia"
  network_interface_ids           = [azurerm_network_interface.app.id]
  disable_password_authentication = true
  admin_ssh_key {
    username   = "vigia"
    public_key = var.chave_ssh_publica
  }
  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
  os_disk {
    caching              = "ReadWrite"
    storage_account_type = var.disco_tipo
    disk_size_gb         = var.disco_gb
  }
  secure_boot_enabled = true
  vtpm_enabled        = true
  identity { type = "SystemAssigned" }
  boot_diagnostics {}
  custom_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tftpl", {}))
  lifecycle { ignore_changes = [custom_data] }
  tags = local.tags
}
resource "azurerm_container_registry" "app" {
  name                   = "acrvigiachuva${random_string.sufixo.result}"
  resource_group_name    = azurerm_resource_group.app.name
  location               = var.localizacao
  sku                    = "Basic"
  admin_enabled          = false
  anonymous_pull_enabled = false
  tags                   = local.tags
}
resource "azurerm_role_assignment" "acr_vm" {
  scope                = azurerm_container_registry.app.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_linux_virtual_machine.app.identity[0].principal_id
}
resource "azurerm_key_vault" "app" {
  name                       = "kv-vigia-${random_string.sufixo.result}"
  location                   = var.localizacao
  resource_group_name        = azurerm_resource_group.app.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = false
  soft_delete_retention_days = 7
  network_acls {
    default_action             = "Deny"
    bypass                     = "AzureServices"
    ip_rules                   = ["${var.ip_operador}/32"]
    virtual_network_subnet_ids = [azurerm_subnet.app.id]
  }
  tags = local.tags
}
resource "azurerm_role_assignment" "kv_operator" {
  scope                = azurerm_key_vault.app.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}
resource "azurerm_role_assignment" "kv_vm" {
  scope                = azurerm_key_vault.app.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_virtual_machine.app.identity[0].principal_id
}
resource "time_sleep" "kv_rbac" {
  create_duration = "60s"
  depends_on      = [azurerm_role_assignment.kv_operator]
}
resource "random_password" "postgres" {
  length  = 40
  special = false
}
resource "random_password" "hash" {
  length  = 64
  special = false
}
resource "random_password" "metrics" {
  length  = 40
  special = false
}
resource "azurerm_key_vault_secret" "postgres" {
  name            = "postgres-password"
  value           = random_password.postgres.result
  key_vault_id    = azurerm_key_vault.app.id
  content_type    = "text/plain"
  expiration_date = "2027-06-30T00:00:00Z"
  depends_on      = [time_sleep.kv_rbac]
}
resource "azurerm_key_vault_secret" "hash" {
  name            = "ip-hash-secret"
  value           = random_password.hash.result
  key_vault_id    = azurerm_key_vault.app.id
  content_type    = "text/plain"
  expiration_date = "2027-06-30T00:00:00Z"
  depends_on      = [time_sleep.kv_rbac]
}
resource "azurerm_key_vault_secret" "metrics" {
  name            = "metrics-token"
  value           = random_password.metrics.result
  key_vault_id    = azurerm_key_vault.app.id
  content_type    = "text/plain"
  expiration_date = "2027-06-30T00:00:00Z"
  depends_on      = [time_sleep.kv_rbac]
}
resource "azurerm_user_assigned_identity" "deploy" {
  name                = "id-vigia-deploy"
  location            = var.localizacao
  resource_group_name = azurerm_resource_group.app.name
  tags                = local.tags
}
resource "azurerm_federated_identity_credential" "github" {
  name                = "github-producao"
  resource_group_name = azurerm_resource_group.app.name
  parent_id           = azurerm_user_assigned_identity.deploy.id
  issuer              = "https://token.actions.githubusercontent.com"
  audience            = ["api://AzureADTokenExchange"]
  subject             = "repo:${var.repositorio_github}:environment:producao"
}
resource "azurerm_role_assignment" "acr_push" {
  scope                = azurerm_container_registry.app.id
  role_definition_name = "AcrPush"
  principal_id         = azurerm_user_assigned_identity.deploy.principal_id
}
resource "azurerm_role_definition" "deploy_vm" {
  name        = "Vigia Chuva - deploy na VM"
  scope       = azurerm_resource_group.app.id
  description = "Executa Run Command na VM do MVP."
  permissions {
    actions     = ["Microsoft.Compute/virtualMachines/read", "Microsoft.Compute/virtualMachines/runCommand/action"]
    not_actions = []
  }
  assignable_scopes = [azurerm_resource_group.app.id]
}
resource "azurerm_role_assignment" "deploy_vm" {
  scope              = azurerm_linux_virtual_machine.app.id
  role_definition_id = azurerm_role_definition.deploy_vm.role_definition_resource_id
  principal_id       = azurerm_user_assigned_identity.deploy.principal_id
}
resource "azurerm_consumption_budget_subscription" "monthly" {
  name            = "vigia-chuva-mensal"
  subscription_id = data.azurerm_client_config.current.subscription_id
  amount          = var.limite_orcamento_usd
  time_grain      = "Monthly"
  time_period {
    start_date = "2026-11-01T00:00:00Z"
    end_date   = "2027-06-30T00:00:00Z"
  }
  notification {
    enabled       = true
    threshold     = 50
    operator      = "EqualTo"
    contact_roles = [var.contato_orcamento]
  }
  notification {
    enabled       = true
    threshold     = 90
    operator      = "EqualTo"
    contact_roles = [var.contato_orcamento]
  }
  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_roles  = [var.contato_orcamento]
  }
}

