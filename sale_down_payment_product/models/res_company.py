from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    sale_down_payment_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Down Payment Product",
        domain=[
            ("type", "=", "service"),
            ("invoice_policy", "=", "order"),
            ("sale_ok", "=", True),
        ],
        check_company=True,
        ondelete="restrict",
        copy=False,
        help="Product assigned to new percentage and fixed-amount down payments. "
        "Leave empty to use Odoo's standard behavior without a product.",
    )

    def _get_sale_down_payment_product(self):
        """Validate again at use time in case the product was subsequently edited."""
        self.ensure_one()
        product = self.sale_down_payment_product_id
        if product and (
            not product.active
            or not product.sale_ok
            or product.type != "service"
            or product.invoice_policy != "order"
            or (product.company_id and product.company_id != self)
        ):
            raise ValidationError(
                _(
                    "The down payment product for %(company)s must be an active, "
                    "saleable service invoiced on ordered quantities, shared or "
                    "belonging to that company. Update it in Sales > Configuration "
                    "> Settings.",
                    company=self.display_name,
                )
            )
        return product

    @api.constrains("sale_down_payment_product_id")
    def _check_sale_down_payment_product_id(self):
        for company in self:
            company._get_sale_down_payment_product()
