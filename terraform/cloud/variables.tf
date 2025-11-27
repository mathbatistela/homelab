# Cloudflare variables
variable "cloudflare_email" {
  description = "Cloudflare account email."
  type        = string
}

variable "cloudflare_api_key" {
  description = "Cloudflare API key with permissions to manage DNS records."
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for the domain you want to manage."
  type        = string
}

variable "racknerd_v0_ip" {
  description = "RackNerd v0 IP address to be used in the DNS record."
  type        = string
}

# AWS variables (optional - set when you need AWS resources)
variable "aws_region" {
  description = "AWS region for resources."
  type        = string
  default     = "us-east-1"
}

variable "aws_access_key" {
  description = "AWS access key ID."
  type        = string
  sensitive   = true
  default     = ""
}

variable "aws_secret_key" {
  description = "AWS secret access key."
  type        = string
  sensitive   = true
  default     = ""
}
