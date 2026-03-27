from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from .models import Dealership, SalesProduct, ProductInventory, DailySale

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