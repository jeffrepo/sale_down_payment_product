from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sale_down_payment_product_id = fields.Many2one(
        related="company_id.sale_down_payment_product_id",
        readonly=False,
    )
