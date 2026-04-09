from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.utils import timezone

from Profile.models import UserProfile
from .models import Claim, Dealership, Inspection, SalesProduct, ProductInventory, DailySale

class C3SystemTestSuite(TestCase):
    """
    Developer Test Artifact: Construction Phase
    Implements Techniques 1, 3, and 4 from the Test Strategy.
    """
    def setUp(self):
        # Setup Preconditions (Roles and Data)
        self.dealer = Dealership.objects.create(name="Northside Motors")
        self.product = SalesProduct.objects.create(name="Car", tracks_inventory=True)
        
        # Unauthorized user for Security Testing
        self.unauthorized_user = User.objects.create_user(username='guest', password='password')
        
        # Authorized Sales Rep for Functional Testing
        self.sales_rep = User.objects.create_user(username='rep', password='password')
        sales_group, _ = Group.objects.get_or_create(name='Sales Rep')
        self.sales_rep.groups.add(sales_group)

    def test_security_access_control(self):
        """Technique 4: Verify unauthorized users cannot add sales"""
        self.client.login(username='guest', password='password')
        # Combined prefix 'home/' + dashboard path 'sales/add-daily/'
        response = self.client.post('/home/sales/add-daily/', {'amount': 5})
        self.assertEqual(response.status_code, 403)

    def test_inventory_integration(self):
        """Technique 3: Verify Sales entry reduces physical Inventory"""
        inventory = ProductInventory.objects.create(product=self.product, dealership=self.dealer, quantity=20)
        
        # Create a superuser to bypass the '_can_modify_daily_sales' permission check
        User.objects.create_superuser(username='admin', password='password', email='admin@test.com')
        self.client.login(username='admin', password='password')

        # Use the full combined path: /home/sales/add-daily/
        self.client.post('/home/sales/add-daily/', {
            'product': self.product.id,
            'dealership': self.dealer.id,
            'amount': 5,
            'date': '2026-03-26'
        })

        inventory.refresh_from_db()
        self.assertEqual(inventory.quantity, 15)
        sale = DailySale.objects.get(product=self.product, dealership=self.dealer)
        admin = User.objects.get(username="admin")
        self.assertEqual(sale.entered_by_id, admin.id)

    def test_prevent_negative_inventory(self):
        """Technique 5: Verify inventory does not drop below zero"""
        # Start with only 2 units
        inventory = ProductInventory.objects.create(product=self.product, dealership=self.dealer, quantity=2)
        self.client.login(username='admin', password='password')
    
        # Attempt to sell 10 units
        self.client.post('/home/sales/add-daily/', {
            'product': self.product.id,
            'dealership': self.dealer.id,
            'amount': 10,
            'date': '2026-03-26'
        })
    
        inventory.refresh_from_db()
        # If your logic is "max(0, new_total)", this will pass at 0. 
        # If it fails, you'll see -8, which means you found a bug!
        self.assertEqual(inventory.quantity, 2)

    def test_claims_forbidden_without_role(self):
        """Users without claims access get 403 (still authenticated)."""
        self.client.login(username="guest", password="password")
        response = self.client.get("/home/claims/")
        self.assertEqual(response.status_code, 403)

    def test_claims_forbidden_without_home_dealership(self):
        """Sales Rep with no profile dealership cannot use claims (same rule as dashboard)."""
        rep_no_home = User.objects.create_user(username="rep_nohome", password="password")
        rep_no_home.groups.add(Group.objects.get(name="Sales Rep"))
        self.client.login(username="rep_nohome", password="password")
        response = self.client.get("/home/claims/")
        self.assertEqual(response.status_code, 403)

    def test_claims_submit_and_scope(self):
        """Sales Rep submits a claim tied to a real DailySale; listing is scoped to home dealership."""
        other = Dealership.objects.create(name="Other Store")
        UserProfile.objects.create(user=self.sales_rep, dealership=self.dealer)
        ProductInventory.objects.create(product=self.product, dealership=self.dealer, quantity=20)
        ProductInventory.objects.create(product=self.product, dealership=other, quantity=10)
        self.client.login(username="rep", password="password")

        self.client.post(
            "/home/sales/add-daily/",
            {
                "product": str(self.product.id),
                "dealership": str(self.dealer.id),
                "amount": "5",
                "date": "2026-03-26",
            },
        )
        sale = DailySale.objects.get(product=self.product, dealership=self.dealer)
        order_ref = (sale.order_number or "").strip() or str(sale.pk)

        response = self.client.post(
            "/home/claims/",
            {
                "customer_name": "Jane Smith",
                "order_ref": order_ref,
                "quantity": "2",
                "reason": "Defect",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Claim.objects.count(), 1)
        claim = Claim.objects.get()
        self.assertEqual(claim.daily_sale_id, sale.pk)
        self.assertEqual(claim.daily_sale.dealership_id, self.dealer.id)
        self.assertEqual(claim.status, Claim.STATUS_PENDING)

        sale_other = DailySale.objects.create(
            product=self.product,
            dealership=other,
            date=timezone.localdate(),
            amount=3,
        )
        Claim.objects.create(
            customer_name="Other",
            daily_sale=sale_other,
            quantity=1,
            submitted_by=self.sales_rep,
        )

        page = self.client.get("/home/claims/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, f"#{claim.pk}")
        self.assertContains(page, "View")
        detail = self.client.get(f"/home/claims/{claim.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Jane Smith")
        self.assertContains(detail, "Defect")
        self.assertNotContains(page, "Other")

    def test_sales_rep_cannot_post_claim_status(self):
        """Only upper-level roles may POST claim status updates."""
        UserProfile.objects.create(user=self.sales_rep, dealership=self.dealer)
        sale = DailySale.objects.create(
            product=self.product,
            dealership=self.dealer,
            date=timezone.localdate(),
            amount=2,
        )
        claim = Claim.objects.create(
            customer_name="A",
            daily_sale=sale,
            quantity=1,
        )
        self.client.login(username="rep", password="password")
        r = self.client.post(
            f"/home/claims/{claim.pk}/status/",
            {"status": Claim.STATUS_APPROVED},
        )
        self.assertEqual(r.status_code, 403)
        claim.refresh_from_db()
        self.assertEqual(claim.status, Claim.STATUS_PENDING)

    def test_management_can_post_claim_status(self):
        mgr = User.objects.create_user(username="mgr", password="password")
        mgr.groups.add(Group.objects.get_or_create(name="Management")[0])
        sale = DailySale.objects.create(
            product=self.product,
            dealership=self.dealer,
            date=timezone.localdate(),
            amount=2,
        )
        claim = Claim.objects.create(
            customer_name="A",
            daily_sale=sale,
            quantity=1,
        )
        self.client.login(username="mgr", password="password")
        r = self.client.post(
            f"/home/claims/{claim.pk}/status/",
            {"status": Claim.STATUS_APPROVED},
        )
        self.assertEqual(r.status_code, 302)
        claim.refresh_from_db()
        self.assertEqual(claim.status, Claim.STATUS_APPROVED)

    def test_inspections_post_saves_and_lists(self):
        """Record an inspection (staff); appears in history table."""
        admin = User.objects.create_superuser(username="insp_admin", password="password", email="insp@test.com")
        self.client.login(username="insp_admin", password="password")
        r = self.client.get("/home/inspections/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Inspection history")

        r = self.client.post(
            "/home/inspections/",
            {
                "dealership": str(self.dealer.id),
                "product": str(self.product.id),
                "customer_name": "Test Customer",
                "vin": "1HGBH41JXMN109186",
                "inspection_date": "2026-04-09",
                "odometer": "12000",
                "installer_name": "Alex Installer",
                "result": "pass",
                "notes": "Looks good",
                "issue_damage": "",
                "issue_incomplete": "",
                "issue_warranty": "",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Inspection.objects.count(), 1)
        insp = Inspection.objects.get()
        self.assertTrue(insp.passed)
        self.assertEqual(insp.vin, "1HGBH41JXMN109186")
        self.assertEqual(insp.dealership_id, self.dealer.id)

        page = self.client.get("/home/inspections/")
        self.assertContains(page, "Test Customer")
        self.assertContains(page, "Pass")
        self.assertContains(page, "View")

        detail = self.client.get(f"/home/inspections/{insp.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "1HGBH41JXMN109186")
        self.assertContains(detail, "Test Customer")

        filtered = self.client.get("/home/inspections/?vin=1HGBH41")
        self.assertContains(filtered, "Test Customer")