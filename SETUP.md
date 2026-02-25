# RestroFlow React Setup Guide

## Quick Start (3 steps)

### 1. Install Dependencies
```bash
cd /Users/sepia/restroflo
npm install
```

### 2. Start Development Server
```bash
npm start
```
The app will automatically open at `http://localhost:3000`

### 3. Test the Flow
- **TablePlan** (`/table-plan`): Click any table → saves `current_table` to localStorage
- **CreateOrder** (`/order`): Add items → saves order to `rf_orders` localStorage
- **Billing** (`/billing`): View bill, split costs, pay → order status becomes 'completed'

---

## Architecture Overview

### Data Flow
```
TablePlan
    ↓ (saves current_table)
    ↓ (navigate to /order)
CreateOrder
    ↓ (saves order to rf_orders)
    ↓ (navigate to /billing)
Billing
    ↓ (reads current_table & rf_orders)
    ↓ (calculate taxes & grand total)
    ↓ (payment → order status: completed)
```

### localStorage Structure
```javascript
// Current Table
localStorage.current_table = "4"  // Table number

// Orders Array
localStorage.rf_orders = [
  {
    id: "ORD1708873456789",
    tableNumber: 4,
    items: [
      { code: "paneer-tikka", name: "Paneer Tikka", price: 250, station: "grill" },
      { code: "butter-paneer", name: "Butter Paneer Masala", price: 320, station: "curry" }
    ],
    created: "2/25/2026, 2:30:56 PM",
    status: "completed",  // or "pending"
    paymentMethod: "card",
    paidAt: "2/25/2026, 2:35:10 PM"
  }
]
```

---

## Component Specifications

### TablePlan.jsx
**Route**: `/table-plan`

**Key Features**:
- 12 mock tables with status (available/occupied/reserved/cleaning)
- Location filter dropdown (All/Indoor/Patio)
- Responsive grid layout (gap: 48px)

**User Action Flow**:
```javascript
User clicks table
  ↓
localStorage.setItem('current_table', JSON.stringify(tableNumber))
  ↓
navigate('/order')
```

---

### CreateOrder.jsx
**Route**: `/order`

**Key Features**:
- Displays: "Ordering for Table {number}"
- 8 menu categories with 25+ vegetarian items
- Add/remove items with quantity tracking
- Real-time order summary panel

**On Mount**:
```javascript
useEffect(() => {
  const table = localStorage.getItem('current_table');
  setCurrentTable(JSON.parse(table));
}, []);
```

**On "Place Order" Click**:
```javascript
const orderObject = {
  id: 'ORD' + Date.now(),
  tableNumber: currentTable,
  items: selectedItems,
  created: new Date().toLocaleString(),
  status: 'pending'
};

const existingOrders = JSON.parse(localStorage.getItem('rf_orders') || '[]');
existingOrders.push(orderObject);
localStorage.setItem('rf_orders', JSON.stringify(existingOrders));

navigate('/billing');
```

---

### Billing.jsx
**Route**: `/billing`

**On Mount**:
```javascript
useEffect(() => {
  const table = localStorage.getItem('current_table');
  const orders = JSON.parse(localStorage.getItem('rf_orders') || '[]');
  
  const activeOrder = orders.find(
    o => o.tableNumber === table && o.status === 'pending'
  );
  
  setActiveOrder(activeOrder);
  calculateTotals(activeOrder.items);
}, []);
```

**Tax Calculation Logic**:
```javascript
subtotal = sum of all item prices
cgst = Math.round(subtotal × 0.025)      // 2.5%
sgst = Math.round(subtotal × 0.025)      // 2.5%
serviceCharge = Math.round(subtotal × 0.05) // 5%
grandTotal = subtotal + cgst + sgst + serviceCharge
```

**Split Bill Calculation**:
```javascript
splitCost = Math.round(grandTotal / numberOfPeople)
```

**On Payment**:
```javascript
Order status: pending → completed
paymentMethod: (cash/card/upi)
paidAt: current timestamp

// Update localStorage
const updatedOrders = orders.map(o => 
  o.id === activeOrder.id 
    ? { ...o, status: 'completed', paymentMethod, paidAt }
    : o
);
localStorage.setItem('rf_orders', JSON.stringify(updatedOrders));
```

---

## Menu Structure (50+ Items)

| Category | Items | Example |
|----------|-------|---------|
| Starters | 4 | Paneer Tikka (₹250), Samosa (₹120) |
| Main Course | 4 | Butter Paneer (₹320), Biryani (₹300) |
| North Indian | 4 | Naan (₹80), Paratha (₹90-100) |
| South Indian | 4 | Dosa (₹140), Idli (₹80) |
| Chinese | 4 | Fried Rice (₹180), Noodles (₹170) |
| Italian | 4 | Pizza (₹280-320), Pasta (₹200-240) |
| Continental | 4 | Burger (₹150), Wrap (₹160-180) |
| Beverages | 6 | Cold Coffee (₹140), Lassi (₹100-140) |
| Desserts | 5 | Gulab Jamun (₹120), Ice Cream (₹80-100) |

---

## Available npm Scripts

```bash
npm start          # Start dev server (port 3000)
npm run build      # Build for production
npm test           # Run tests
npm eject          # Eject from create-react-app (irreversible)
```

---

## Browser DevTools Debugging

### View localStorage in Console
```javascript
// All orders
JSON.parse(localStorage.getItem('rf_orders'))

// Current table
JSON.parse(localStorage.getItem('current_table'))

// Clear all data (testing)
localStorage.clear()
```

### Test Calculation
```javascript
const items = [
  { price: 250 },
  { price: 320 }
];
const subtotal = items.reduce((s, i) => s + i.price, 0);  // 570
const cgst = Math.round(subtotal * 0.025);                // 14
const sgst = Math.round(subtotal * 0.025);                // 14
const service = Math.round(subtotal * 0.05);              // 29
console.log(subtotal + cgst + sgst + service);            // 627
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `npm install` fails | Clear cache: `npm cache clean --force` |
| Port 3000 already in use | Kill process: `lsof -i :3000` then `kill -9 <PID>` |
| localStorage empty | Check browser DevTools → Application → Storage |
| Navigate not working | Ensure `useNavigate` hook is imported from `react-router-dom` |
| Styles not applied | Clear browser cache (Cmd+Shift+Delete) |

---

## Responsive Design

- **Desktop**: Full 2-column layouts, grid gaps
- **Tablet (≤768px)**: Single column, adjusted grid sizes
- **Mobile**: Touch-friendly buttons, smaller fonts

---

## What's Next?

1. Replace static `.html` files with this React app
2. Deploy to Vercel/Netlify with: `npm run build`
3. Add backend API endpoints for:
   - Save orders to database
   - Payment processing
   - Order history persistence
   - Email notifications

---

**Questions?** Refer to the main README.md for detailed component documentation.
