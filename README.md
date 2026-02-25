# RestroFlow - React Ordering System

A seamless customer ordering flow for restaurant table service with React Router navigation and localStorage data persistence.

## Project Structure

```
src/
├── components/
│   ├── TablePlan.jsx          # Step 1: Select table
│   ├── TablePlan.css
│   ├── CreateOrder.jsx        # Step 2: Create order
│   ├── CreateOrder.css
│   ├── Billing.jsx            # Step 3: View bill & payment
│   └── Billing.css
├── App.jsx                    # Main app with React Router
├── App.css
└── index.jsx                  # Entry point
public/
├── index.html                 # HTML template
```

## Component Flow

### 1. TablePlan Component (Step 1)
- **Route**: `/table-plan`
- **Action**: User clicks a table
- **localStorage Save**: 
  ```javascript
  localStorage.setItem('current_table', JSON.stringify(tableNumber))
  ```
- **Navigation**: Auto-redirects to `/order`

### 2. CreateOrder Component (Step 2)
- **Route**: `/order`
- **On Mount**: Reads `current_table` from localStorage
- **Display**: "Ordering for Table {number}"
- **Action**: User adds items and clicks "Place Order"
- **localStorage Operations**:
  - Creates order object: `{ id, tableNumber, items, created, status }`
  - Reads existing orders from `rf_orders` key
  - Pushes new order to array
  - Saves back: `localStorage.setItem('rf_orders', JSON.stringify(updatedOrders))`
- **Navigation**: Auto-redirects to `/billing`

### 3. Billing Component (Step 3)
- **Route**: `/billing`
- **On Mount**: Reads `current_table` and `rf_orders` from localStorage
- **Filtering**: Finds order matching current table with status 'pending'
- **Calculations**:
  - Subtotal: Sum of all item prices
  - CGST (2.5%): `subtotal × 0.025`
  - SGST (2.5%): `subtotal × 0.025`
  - Service Charge (5%): `subtotal × 0.05`
  - Grand Total: `subtotal + cgst + sgst + serviceCharge`
- **Split Bill**: Divides grand total by number of people
- **Payment**: Updates order status to 'completed'
- **Navigation**: Returns to `/table-plan` after payment

## localStorage Keys

| Key | Data Structure | Purpose |
|-----|---|---|
| `current_table` | `number` | Active table number |
| `rf_orders` | `[{ id, tableNumber, items: [], created, status, paymentMethod }]` | All orders |

## Installation & Setup

### Prerequisites
- Node.js (v14+)
- npm or yarn

### Steps

1. **Navigate to project directory**
   ```bash
   cd /Users/sepia/restroflo
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start development server**
   ```bash
   npm start
   ```
   The app will open at `http://localhost:3000`

4. **Build for production**
   ```bash
   npm run build
   ```

## Features

### TablePlan Component
- ✅ Grid layout with 12+ mock tables
- ✅ Filter by location (Indoor/Patio)
- ✅ Status indicators (Available/Occupied/Reserved/Cleaning)
- ✅ Click to select and navigate to order

### CreateOrder Component
- ✅ Display selected table number
- ✅ 8 categorized menu sections
- ✅ 25+ vegetarian items with prices
- ✅ Add/remove items with quantity tracking
- ✅ Real-time order summary
- ✅ Save to localStorage on "Place Order"

### Billing Component
- ✅ Fetch and display active order for table
- ✅ Automatic tax calculations (CGST + SGST + Service)
- ✅ Split bill feature with +/- controls
- ✅ Payment method selection (Cash/Card/UPI)
- ✅ Success message after payment
- ✅ Order status updates to 'completed'

## Styling

- **Color Scheme**:
  - Primary: `#826cd7` (Purple)
  - Background: `#fff8f3` (Light Peach)
  - Text: `#2e2e2e` (Dark Gray)

- **Responsive**: Mobile-friendly with media queries for tablets and phones
- **Modern UI**: Card layouts, smooth transitions, shadow effects

## Technical Details

### Technology Stack
- **React 18+**: Component-based UI
- **React Router v6**: Client-side navigation
- **localStorage API**: Data persistence
- **CSS3**: Responsive styling

### Key Functions

**TablePlan.jsx**
```javascript
handleTableClick(tableNumber) {
  localStorage.setItem('current_table', JSON.stringify(tableNumber));
  navigate('/order');
}
```

**CreateOrder.jsx**
```javascript
handlePlaceOrder() {
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
}
```

**Billing.jsx**
```javascript
calculateTotals(items) {
  const subtotal = items.reduce((sum, item) => sum + item.price, 0);
  const cgst = Math.round(subtotal * 0.025);
  const sgst = Math.round(subtotal * 0.025);
  const serviceCharge = Math.round(subtotal * 0.05);
  const grandTotal = subtotal + cgst + sgst + serviceCharge;
  // ... state updates
}
```

## Testing the Flow

1. **Start at `/table-plan`** → Select "Table 1"
2. **Redirects to `/order`** → Add items (e.g., Paneer Tikka, Butter Paneer)
3. **Click "Place Order"** → Redirects to `/billing`
4. **Adjust split bill** → Select payment method
5. **Click "Pay"** → Success message → Redirect to `/table-plan`

## Browser DevTools Inspection

Check localStorage contents in DevTools:
```javascript
// View all orders
console.log(JSON.parse(localStorage.getItem('rf_orders')));

// View current table
console.log(JSON.parse(localStorage.getItem('current_table')));
```

## License

MIT License - Feel free to use and modify this project.
