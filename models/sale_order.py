from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _prepare_down_payment_line_values_from_base_line(self, base_line):
        values = super()._prepare_down_payment_line_values_from_base_line(base_line)
        product = self.company_id._get_sale_down_payment_product()
        if product:
            values.update(
                product_id=product.id,
                product_uom_id=product.uom_id.id,
                # The amount already includes the source order's discounts.
                # A pricelist rule on this product must not discount it again.
                discount=0.0,
            )
        # Preserve Odoo's price, taxes, analytic distribution and extra tax data.
        # Native invoice preparation copies this product to the advance invoice
        # and to its deduction on the final invoice.
        return values
