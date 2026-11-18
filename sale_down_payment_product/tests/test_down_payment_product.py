from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.sale.tests.common import TestSaleCommon


@tagged("post_install", "-at_install")
class TestDownPaymentProduct(TestSaleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.tax = cls.tax_sale_a.copy({"name": "Order tax 12%", "amount": 12.0})
        cls.product_tax = cls.tax.copy({"name": "Product tax 77%", "amount": 77.0})
        cls.advance_account = cls.env["account.account"].create({
            "name": "Customer advances",
            "code": "TESTADVANCE",
            "account_type": "liability_current",
            "reconcile": True,
        })
        cls.company.downpayment_account_id = cls.advance_account
        cls.sale_product = cls.env["product.product"].create({
            "name": "Ordered service",
            "type": "service",
            "invoice_policy": "order",
            "list_price": 1000.0,
            "categ_id": cls.product_category.id,
            "property_account_income_id": cls.company_data["default_account_revenue"].id,
            "taxes_id": [Command.set(cls.tax.ids)],
        })
        cls.advance_product = cls._create_advance_product()
        cls.company.sale_down_payment_product_id = cls.advance_product

    @classmethod
    def _create_advance_product(cls, company=None, **values):
        # Create variants explicitly: product.product.copy() delegates to the
        # template and inherits the create_product_product context from create().
        return cls.env["product.product"].with_company(company or cls.company).create({
            "name": "Anticipo de clientes",
            "type": "service",
            "invoice_policy": "order",
            "sale_ok": True,
            "list_price": 9999.0,
            "categ_id": cls.product_category.id,
            "property_account_income_id": cls.company_data["default_account_expense"].id,
            "taxes_id": [Command.set(cls.product_tax.ids)],
            "supplier_taxes_id": [Command.clear()],
            **values,
        })

    def _new_order(self, taxes=None, company=None, extra_lines=None, **values):
        company = company or self.company
        taxes = self.tax if taxes is None else taxes
        order = self.env["sale.order"].with_company(company).create({
            "partner_id": self.partner_a.id,
            "company_id": company.id,
            "order_line": [
                Command.create({
                    "product_id": self.sale_product.id,
                    "product_uom_qty": 1.0,
                    "price_unit": 1000.0,
                    "tax_ids": [Command.set(taxes.ids)],
                }),
                *(extra_lines or []),
            ],
            **values,
        })
        order.action_confirm()
        return order

    def _invoice(self, order, method="percentage", amount=30.0):
        wizard = self.env["sale.advance.payment.inv"].create({
            "sale_order_ids": [Command.set(order.ids)],
            "advance_payment_method": method,
            "amount": amount if method == "percentage" else 0.0,
            "fixed_amount": amount if method == "fixed" else 0.0,
        })
        action = wizard.create_invoices()
        return self.env["account.move"].browse(action["res_id"])

    def _post(self, invoice):
        invoice.invoice_date = fields.Date.today()
        invoice.action_post()

    def _assert_product(self, invoice, product):
        lines = invoice.invoice_line_ids.filtered("is_downpayment")
        self.assertTrue(lines)
        self.assertEqual(lines.product_id, product)
        self.assertTrue(all(line.product_id == product for line in lines))
        self.assertTrue(all(line.product_uom_id == product.uom_id for line in lines))
        self.assertTrue(all(line.sale_line_ids.product_id == product for line in lines))
        return lines

    def test_percentage_and_final_deduction(self):
        order = self._new_order()
        advance = self._invoice(order)
        lines = self._assert_product(advance, self.advance_product)
        self.assertAlmostEqual(advance.amount_untaxed, 300.0)
        self.assertAlmostEqual(advance.amount_total, 336.0)
        self.assertEqual(lines.tax_ids, self.tax)
        self.assertEqual(lines.account_id, self.advance_account)
        self.assertEqual(lines.quantity, 1.0)
        self.assertEqual(lines.discount, 0.0)
        self.assertAlmostEqual(order.amount_total, 1120.0)
        self.assertEqual(lines.sale_line_ids.product_uom_qty, 0.0)
        self.assertFalse(order.order_line.filtered("display_type").product_id)
        self._post(advance)
        final = self._invoice(order, "delivered")
        deductions = self._assert_product(final, self.advance_product)
        self.assertEqual(deductions.account_id, self.advance_account)
        self.assertLess(deductions.price_subtotal, 0.0)
        self.assertAlmostEqual(final.amount_total, 784.0)
        self._post(final)

    def test_fixed_amount_and_final_deduction(self):
        order = self._new_order()
        advance = self._invoice(order, "fixed", 224.0)
        self._assert_product(advance, self.advance_product)
        self.assertAlmostEqual(advance.amount_total, 224.0)
        self._post(advance)
        final = self._invoice(order, "delivered")
        self._assert_product(final, self.advance_product)
        self.assertAlmostEqual(final.amount_total, 896.0)
        self._post(final)

    def test_no_configuration_keeps_native_behavior(self):
        self.company.sale_down_payment_product_id = False
        for method, amount in (("percentage", 30.0), ("fixed", 336.0)):
            with self.subTest(method=method):
                order = self._new_order()
                advance = self._invoice(order, method, amount)
                self.assertFalse(advance.invoice_line_ids.product_id)
                self.assertAlmostEqual(advance.amount_total, 336.0)

    def test_regular_invoice_uses_original_product(self):
        invoice = self._invoice(self._new_order(), "delivered")
        self.assertEqual(invoice.invoice_line_ids.product_id, self.sale_product)
        self.assertFalse(invoice.invoice_line_ids.is_downpayment)
        self.assertAlmostEqual(invoice.amount_total, 1120.0)

    def test_mixed_taxes_and_rounding_match_native_behavior(self):
        extra_lines = [Command.create({
            "product_id": self.sale_product.id,
            "product_uom_qty": 3.0,
            "price_unit": 91.37,
            "discount": 7.0,
            "tax_ids": [Command.clear()],
        })]
        for rounding in ("round_per_line", "round_globally"):
            for method, amount in (("percentage", 33.33), ("fixed", 300.01)):
                with self.subTest(rounding=rounding, method=method):
                    self.company.tax_calculation_rounding_method = rounding
                    self.company.sale_down_payment_product_id = False
                    baseline = self._invoice(self._new_order(extra_lines=extra_lines), method, amount)
                    self.company.sale_down_payment_product_id = self.advance_product
                    order = self._new_order(extra_lines=extra_lines)
                    advance = self._invoice(order, method, amount)
                    self._assert_product(advance, self.advance_product)
                    self.assertEqual(len(advance.invoice_line_ids), len(baseline.invoice_line_ids))
                    self.assertEqual(advance.amount_untaxed, baseline.amount_untaxed)
                    self.assertEqual(advance.amount_tax, baseline.amount_tax)
                    self.assertEqual(advance.amount_total, baseline.amount_total)
                    self.assertEqual(advance.invoice_line_ids.tax_ids, baseline.invoice_line_ids.tax_ids)
                    self._post(advance)
                    final = self._invoice(order, "delivered")
                    self._assert_product(final, self.advance_product)
                    self.assertAlmostEqual(final.amount_total + advance.amount_total, order.amount_total)

    def test_price_included_tax(self):
        included_tax = self.tax.copy({"price_include_override": "tax_included"})
        for method, amount in (("percentage", 25.0), ("fixed", 250.0)):
            with self.subTest(method=method):
                order = self._new_order(taxes=included_tax)
                advance = self._invoice(order, method, amount)
                self._assert_product(advance, self.advance_product)
                self.assertAlmostEqual(advance.amount_total, 250.0)
                self._post(advance)
                final = self._invoice(order, "delivered")
                self.assertAlmostEqual(final.amount_total, 750.0)

    def test_native_account_fallback_ignores_advance_product_account(self):
        self.company.downpayment_account_id = False
        invoice = self._invoice(self._new_order())
        self._assert_product(invoice, self.advance_product)
        self.assertEqual(invoice.invoice_line_ids.account_id, self.sale_product.property_account_income_id)

    def test_fiscal_position_maps_down_payment_account(self):
        mapped_account = self.advance_account.copy({"code": "TESTADVMAPPED"})
        fiscal_position = self.env["account.fiscal.position"].create({
            "name": "Mapped advance account",
            "company_id": self.company.id,
            "account_ids": [Command.create({
                "account_src_id": self.advance_account.id,
                "account_dest_id": mapped_account.id,
            })],
        })
        invoice = self._invoice(self._new_order(fiscal_position_id=fiscal_position.id))
        self._assert_product(invoice, self.advance_product)
        self.assertEqual(invoice.invoice_line_ids.account_id, mapped_account)

    def test_pricelist_does_not_discount_advance_product(self):
        pricelist = self.env["product.pricelist"].create({
            "name": "Advance product discount",
            "currency_id": self.company.currency_id.id,
            "item_ids": [Command.create({
                "applied_on": "0_product_variant",
                "product_id": self.advance_product.id,
                "compute_price": "percentage",
                "percent_price": 50.0,
            })],
        })
        order = self._new_order(pricelist_id=pricelist.id)
        invoice = self._invoice(order)
        self.assertEqual(invoice.invoice_line_ids.discount, 0.0)
        self.assertAlmostEqual(invoice.amount_total, 336.0)

    def test_changing_configuration_preserves_existing_deductions(self):
        order = self._new_order()
        first = self._invoice(order, "fixed", 112.0)
        self._post(first)
        other_product = self._create_advance_product(name="New advance product")
        self.company.sale_down_payment_product_id = other_product
        second = self._invoice(order, "fixed", 224.0)
        self._assert_product(second, other_product)
        self._post(second)
        self.company.sale_down_payment_product_id = False
        final = self._invoice(order, "delivered")
        deductions = final.invoice_line_ids.filtered("is_downpayment")
        self.assertEqual(deductions.product_id, self.advance_product | other_product)
        self.assertAlmostEqual(final.amount_total, 784.0)

    def test_settings_write_to_selected_company(self):
        self.company.sale_down_payment_product_id = False
        settings = self.env["res.config.settings"].create({
            "company_id": self.company.id,
            "sale_down_payment_product_id": self.advance_product.id,
        })
        self.assertEqual(self.company.sale_down_payment_product_id, self.advance_product)
        settings.sale_down_payment_product_id = False
        self.assertFalse(self.company.sale_down_payment_product_id)

    def test_invalid_product_configuration_is_rejected(self):
        for values in (
            {"type": "consu"},
            {"invoice_policy": "delivery"},
            {"sale_ok": False},
            {"active": False},
        ):
            with self.subTest(values=values):
                product = self._create_advance_product(**values)
                with self.assertRaises(ValidationError), self.cr.savepoint():
                    self.company.sale_down_payment_product_id = product

    def test_edited_or_archived_product_blocks_new_advance(self):
        for values in ({"active": False}, {"invoice_policy": "delivery"}):
            with self.subTest(values=values):
                order = self._new_order()
                with self.assertRaises(ValidationError), self.cr.savepoint():
                    self.advance_product.write(values)
                    self._invoice(order)
                self.assertFalse(order.invoice_ids)
                self.assertFalse(order.order_line.filtered("is_downpayment"))

    def test_order_company_determines_product(self):
        other_data = self.setup_other_company(name="Second company")
        other_company = other_data["company"]
        other_product = self._create_advance_product(company=other_company, **{
            "name": "Second company advances",
            "company_id": other_company.id,
            "taxes_id": [Command.clear()],
            "supplier_taxes_id": [Command.clear()],
            "property_account_income_id": other_data["default_account_revenue"].id,
        })
        other_company.sale_down_payment_product_id = other_product
        other_company.downpayment_account_id = other_data["default_account_revenue"]
        order = self._new_order(taxes=self.env["account.tax"], company=other_company)
        # The wizard starts in the first company, while the order belongs to the second.
        self.assertEqual(self.env.company, self.company)
        invoice = self._invoice(order, "fixed", 100.0)
        self._assert_product(invoice, other_product)
        self.assertEqual(invoice.company_id, other_company)
        self.assertEqual(self.company.sale_down_payment_product_id, self.advance_product)
        with self.assertRaises(UserError), self.cr.savepoint():
            self.company.sale_down_payment_product_id = other_product
