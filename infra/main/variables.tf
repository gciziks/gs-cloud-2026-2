variable "localizacao" {
  type    = string
  default = "northcentralus"
}
variable "projeto" {
  type    = string
  default = "vigia-chuva"
}
variable "tamanho_vm" {
  type    = string
  default = "Standard_B2ats_v2"
}
variable "repositorio_github" {
  type    = string
  default = "gciziks/gs-cloud-2026-2"
}
variable "github_oidc_subject" {
  type        = string
  default     = null
  description = "Subject apresentado pelo GitHub, incluindo IDs imutáveis quando habilitados."
}
variable "ip_operador" {
  type = string
  validation {
    condition     = can(cidrnetmask("${var.ip_operador}/32"))
    error_message = "Informe IPv4 sem mascara."
  }
}
variable "chave_ssh_publica" {
  type      = string
  sensitive = true
}
variable "contato_orcamento" {
  type        = string
  default     = "Owner"
  description = "Role para alertas de custo; email pessoal pode ficar apenas no tfvars local."
}
variable "limite_orcamento" {
  type        = number
  default     = 60
  description = "Valor mensal na moeda de cobrança da assinatura (BRL nesta entrega)."
}
variable "admin_cidr" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.admin_cidr == null ? true : (can(cidrnetmask(var.admin_cidr)) && try(tonumber(split("/", var.admin_cidr)[1]), 0) >= 24)
    error_message = "admin_cidr precisa ser um IP especifico (/24 a /32)."
  }
}

variable "disco_gb" {
  type    = number
  default = 32
  validation {
    condition     = var.disco_gb >= 30 && var.disco_gb <= 1024
    error_message = "disco_gb precisa ficar entre 30 e 1024."
  }
}
variable "disco_tipo" {
  type    = string
  default = "StandardSSD_LRS"
  validation {
    condition     = contains(["Premium_LRS", "StandardSSD_LRS", "Standard_LRS"], var.disco_tipo)
    error_message = "disco_tipo precisa ser Premium_LRS, StandardSSD_LRS ou Standard_LRS."
  }
}
