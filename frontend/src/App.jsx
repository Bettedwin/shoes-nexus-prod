import React, { useState, useEffect } from 'react';
import { ShoppingCart, Search, Menu, X, User, MapPin, Phone, Instagram, Facebook, Twitter, Heart, Check, ArrowRight, Package, TrendingUp, Star, AlertCircle, Loader } from 'lucide-react';

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const POS_URL = import.meta.env.VITE_POS_URL || 'http://localhost:8501';

const getPublicBrand = (product) => product?.public_brand || product?.brand || '';
const getPublicTitle = (product) => (
  product?.public_title || `${product?.brand || ''} ${product?.model || ''}`.trim()
);
const getPublicDescription = (product) => product?.public_description || '';

export default function ShoesNexusEcommerce() {
  // State Management
  const [products, setProducts] = useState([]);
  const [settings, setSettings] = useState(null);
  const [deliveryZones, setDeliveryZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('store');
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [cart, setCart] = useState([]);
  const [wishlist, setWishlist] = useState([]);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [filterCategory, setFilterCategory] = useState('All');
  const [filterType, setFilterType] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSize, setSelectedSize] = useState(null);
  const [newsletterEmail, setNewsletterEmail] = useState('');
  const [showSaleButton, setShowSaleButton] = useState(true);
  const [featuredHourKey, setFeaturedHourKey] = useState(() => Math.floor(Date.now() / 3600000));
  const [sandalsMenuOpen, setSandalsMenuOpen] = useState(false);
  const [blogPosts, setBlogPosts] = useState([]);
  const [selectedBlog, setSelectedBlog] = useState(null);
  const [selectedBlogLoading, setSelectedBlogLoading] = useState(false);
  const [blogCategories, setBlogCategories] = useState([]);
  const [blogCategory, setBlogCategory] = useState('All');
  const [blogPage, setBlogPage] = useState(0);
  const blogPageSize = 6;
  const [homeSections, setHomeSections] = useState([]);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');
  const [authNotice, setAuthNotice] = useState('');
  const [postAuthView, setPostAuthView] = useState('');
  const [toastMessage, setToastMessage] = useState('');
  const [authKind, setAuthKind] = useState(() => {
    try {
      return localStorage.getItem('sn_auth_kind') || 'customer';
    } catch {
      return 'customer';
    }
  });
  const [authToken, setAuthToken] = useState(() => {
    try {
      return localStorage.getItem('sn_auth_token') || '';
    } catch {
      return '';
    }
  });
  const [authUser, setAuthUser] = useState(null);
  const [authForm, setAuthForm] = useState({
    name: '',
    email: '',
    phone: '',
    password: '',
    confirmPassword: '',
    resetToken: '',
    currentPassword: ''
  });
  const [adminProducts, setAdminProducts] = useState([]);
  const [adminStaff, setAdminStaff] = useState([]);
  const [adminSales, setAdminSales] = useState([]);
  const [adminOrders, setAdminOrders] = useState([]);
  const [adminLowStock, setAdminLowStock] = useState([]);
  const [adminAuditLog, setAdminAuditLog] = useState([]);
  const [adminBlogPosts, setAdminBlogPosts] = useState([]);
  const [adminSections, setAdminSections] = useState([]);
  const [adminLoading, setAdminLoading] = useState(false);
  const [adminError, setAdminError] = useState('');
  const [adminProductSearch, setAdminProductSearch] = useState('');
  const [adminExpandedOrders, setAdminExpandedOrders] = useState({});
  const [adminOrderEdits, setAdminOrderEdits] = useState({});
  const [adminRefreshKey, setAdminRefreshKey] = useState(0);
  const [adminProductForm, setAdminProductForm] = useState({
    category: 'Women',
    brand: '',
    model: '',
    color: '',
    image_url: '',
    public_brand: '',
    public_title: '',
    public_description: '',
    buying_price: '',
    selling_price: '',
    sizes: ''
  });
  const [adminEditProduct, setAdminEditProduct] = useState(null);
  const [adminEditForm, setAdminEditForm] = useState({
    category: '',
    brand: '',
    model: '',
    color: '',
    image_url: '',
    public_brand: '',
    public_title: '',
    public_description: '',
    buying_price: '',
    selling_price: '',
    sizes: ''
  });
  const [adminBlogForm, setAdminBlogForm] = useState({
    title: '',
    category: '',
    excerpt: '',
    content: '',
    image_url: '',
    is_published: true
  });
  const [adminEditBlog, setAdminEditBlog] = useState(null);
  const [adminSectionForm, setAdminSectionForm] = useState({
    title: '',
    category_label: '',
    category_match: '',
    model_keywords: '',
    filter_category: 'All',
    filter_type: 'All',
    limit_count: '',
    alternate_brands: false,
    allow_out_of_stock: false,
    sort_order: 0,
    is_active: true
  });
  const [adminEditSection, setAdminEditSection] = useState(null);
  const [adminUserResetForm, setAdminUserResetForm] = useState({
    identifier: '',
    new_password: ''
  });
  const [adminUsers, setAdminUsers] = useState([]);
  const [adminUserSearch, setAdminUserSearch] = useState('');
  const [adminStaffResetForm, setAdminStaffResetForm] = useState({
    username: '',
    new_password: ''
  });
  const [adminUploadLoading, setAdminUploadLoading] = useState(false);
  const [adminStaffForm, setAdminStaffForm] = useState({
    username: '',
    password: '',
    role: 'Cashier'
  });
  const [adminEditingStaff, setAdminEditingStaff] = useState(null);
  const [userOrders, setUserOrders] = useState([]);
  const [userOrdersLoading, setUserOrdersLoading] = useState(false);
  const [userOrdersError, setUserOrdersError] = useState('');

  // Fetch data from backend on mount
  useEffect(() => {
    fetchProducts();
    fetchSettings();
    fetchDeliveryZones();
  }, []);

  // Fetch products when filter changes
  useEffect(() => {
    fetchProducts();
  }, [filterCategory, searchQuery, filterType]);

  useEffect(() => {
    const fetchBlog = async () => {
      try {
        const categoryParam = blogCategory !== 'All' ? `&category=${encodeURIComponent(blogCategory)}` : '';
        const response = await fetch(`${API_BASE_URL}/api/blog?limit=${blogPageSize}&offset=${blogPage * blogPageSize}${categoryParam}`);
        if (!response.ok) return;
        const data = await response.json();
        setBlogPosts(data || []);
      } catch (error) {
        console.error('Error fetching blog posts:', error);
      }
    };
    fetchBlog();
  }, [blogCategory, blogPage]);

  useEffect(() => {
    const fetchBlogCategories = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/blog/categories`);
        if (!response.ok) return;
        const data = await response.json();
        setBlogCategories(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Error fetching blog categories:', error);
      }
    };
    fetchBlogCategories();
  }, []);

  useEffect(() => {
    if (view !== 'blog' || !selectedBlog?.slug) return;
    const fetchSinglePost = async () => {
      try {
        setSelectedBlogLoading(true);
        const response = await fetch(`${API_BASE_URL}/api/blog/${selectedBlog.slug}`);
        if (!response.ok) return;
        const data = await response.json();
        if (data) setSelectedBlog(data);
      } catch (error) {
        console.error('Error fetching blog post:', error);
      } finally {
        setSelectedBlogLoading(false);
      }
    };
    fetchSinglePost();
  }, [view, selectedBlog?.slug]);

  useEffect(() => {
    const fetchHomeSections = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/sections`);
        if (!response.ok) return;
        const data = await response.json();
        setHomeSections(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Error fetching home sections:', error);
      }
    };
    fetchHomeSections();
  }, []);

  const renderBlogContent = (text) => {
    if (!text) return '';
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    // links: [text](url)
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    // bold **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    // italics *text*
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    // inline code `code`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // paragraphs by line breaks
    html = html.split(/\n{2,}/).map(p => `<p>${p.replace(/\n/g, '<br />')}</p>`).join('');
    return html;
  };

  // Rotate featured picks on the hour
  useEffect(() => {
    const updateHourKey = () => setFeaturedHourKey(Math.floor(Date.now() / 3600000));
    const now = Date.now();
    const msToNextHour = 3600000 - (now % 3600000);
    let intervalId;
    const timeoutId = setTimeout(() => {
      updateHourKey();
      intervalId = setInterval(updateHourKey, 3600000);
    }, msToNextHour);
    return () => {
      clearTimeout(timeoutId);
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    if (!authToken) {
      setAuthUser(null);
      return;
    }
    const fetchMe = async () => {
      try {
        if (authKind === 'staff') {
          const response = await fetch(`${API_BASE_URL}/api/auth/staff/me`, {
            headers: { Authorization: `Bearer ${authToken}` }
          });
          if (!response.ok) {
            setAuthUser(null);
            return;
          }
          const data = await response.json();
          setAuthUser({ ...data.staff, isStaff: true });
          return;
        }
        const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
          headers: { Authorization: `Bearer ${authToken}` }
        });
        if (!response.ok) {
          setAuthUser(null);
          return;
        }
        const data = await response.json();
        setAuthUser(data.user);
      } catch {
        setAuthUser(null);
      }
    };
    fetchMe();
  }, [authToken, authKind]);

  useEffect(() => {
    setAuthNotice('');
    setAuthError('');
  }, [authMode, authOpen]);

  useEffect(() => {
    if (!toastMessage) return;
    const timer = setTimeout(() => setToastMessage(''), 2500);
    return () => clearTimeout(timer);
  }, [toastMessage]);

  useEffect(() => {
    if (view !== 'admin') return;
    if (!authUser?.isStaff || authUser?.role?.toLowerCase() !== 'admin') return;
    const fetchAdminData = async () => {
      setAdminLoading(true);
      setAdminError('');
      try {
        const headers = { Authorization: `Bearer ${authToken}` };
        const [productsRes, staffRes, salesRes, ordersRes, blogRes, sectionsRes, usersRes, lowStockRes, auditRes] = await Promise.all([
          fetch(`${API_BASE_URL}/api/admin/products`, { headers }),
          fetch(`${API_BASE_URL}/api/admin/staff`, { headers }),
          fetch(`${API_BASE_URL}/api/admin/sales`, { headers }),
          fetch(`${API_BASE_URL}/api/admin/orders`, { headers }),
          fetch(`${API_BASE_URL}/api/admin/blog`, { headers }),
          fetch(`${API_BASE_URL}/api/admin/sections`, { headers }),
          fetch(`${API_BASE_URL}/api/admin/users`, { headers }),
          fetch(`${API_BASE_URL}/api/admin/low-stock`, { headers }),
          fetch(`${API_BASE_URL}/api/admin/audit-log`, { headers })
        ]);
        if (!productsRes.ok || !staffRes.ok || !salesRes.ok) {
          const errText = await productsRes.text();
          throw new Error(errText || 'Failed to load admin data.');
        }
        const [products, staff, sales, orders, blogPosts, sections, users, lowStock, auditLog] = await Promise.all([
          productsRes.json(),
          staffRes.json(),
          salesRes.json(),
          ordersRes.ok ? ordersRes.json() : [],
          blogRes.ok ? blogRes.json() : [],
          sectionsRes.ok ? sectionsRes.json() : [],
          usersRes.ok ? usersRes.json() : [],
          lowStockRes.ok ? lowStockRes.json() : [],
          auditRes.ok ? auditRes.json() : []
        ]);
        setAdminProducts(products);
        setAdminStaff(staff);
        setAdminSales(sales);
        setAdminOrders(orders);
        setAdminBlogPosts(blogPosts || []);
        setAdminSections(sections || []);
        setAdminUsers(users || []);
        setAdminLowStock(lowStock || []);
        setAdminAuditLog(auditLog || []);
      } catch (error) {
        setAdminError(error?.message || 'Unable to load admin data. Please try again.');
      } finally {
        setAdminLoading(false);
      }
    };
    fetchAdminData();
  }, [view, authUser, authToken, adminRefreshKey]);

  useEffect(() => {
    if (view !== 'account') return;
    if (!authUser || authKind !== 'customer') return;
    const fetchUserOrders = async () => {
      setUserOrdersLoading(true);
      setUserOrdersError('');
      try {
        const response = await fetch(`${API_BASE_URL}/api/orders/me`, {
          headers: { Authorization: `Bearer ${authToken}` }
        });
        if (!response.ok) {
          setUserOrdersError('Unable to load your orders right now.');
          setUserOrders([]);
          return;
        }
        const data = await response.json();
        setUserOrders(Array.isArray(data) ? data : []);
      } catch (error) {
        setUserOrdersError('Unable to load your orders right now.');
        setUserOrders([]);
      } finally {
        setUserOrdersLoading(false);
      }
    };
    fetchUserOrders();
  }, [view, authUser, authKind, authToken]);

  // API Calls
  const fetchProducts = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (filterCategory !== 'All') params.append('category', filterCategory);
      if (searchQuery) params.append('search', searchQuery);

      const response = await fetch(`${API_BASE_URL}/api/products?${params}`);
      let data = await response.json();
      
      // Filter by type on frontend if needed
      if (filterType !== 'All') {
        data = data.filter(product => {
          const productType = product.category.toLowerCase();
          
          if (filterType === 'Sandals') {
            const model = (product.model || '').toLowerCase();
            return productType.includes('sandal') ||
              model.includes('sandal') ||
              model.includes('slide') ||
              model.includes('slides') ||
              model.includes('strap') ||
              model.includes('multi-strap') ||
              model.includes('multistrap') ||
              model.includes('3-strap');
          } else if (filterType === 'Sneakers') {
            const model = (product.model || '').toLowerCase();
            const imageUrl = (product.image_url || '').toLowerCase();
            const brand = (product.brand || '').toLowerCase();
            return productType.includes('sneaker') ||
              model.includes('sneaker') ||
              model.includes('sneakers') ||
              imageUrl.includes('sneaker') ||
              imageUrl.includes('men-sneakers') ||
              imageUrl.includes('women-sneakers') ||
              brand.includes('puma') ||
              brand.includes('nike');
          } else if (filterType === 'Heels') {
            const model = (product.model || '').toLowerCase();
            const imageUrl = (product.image_url || '').toLowerCase();
            const haystack = `${productType} ${model} ${imageUrl}`;
            return haystack.includes('heel') ||
              haystack.includes('heels') ||
              haystack.includes('stiletto') ||
              haystack.includes('stilletto') ||
              haystack.includes('stilleto');
          } else if (filterType === 'Shoes') {
            return productType.includes('shoe') || productType.includes('brogue') || productType.includes('doll');
          } else if (filterType === 'Accessories') {
            return productType.includes('accessories') || productType.includes('gift');
          }
          return true;
        });
      }
      
      setProducts(data);
    } catch (error) {
      console.error('Error fetching products:', error);
      alert('Failed to load products. Make sure backend is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  const fetchSettings = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/settings`);
      const data = await response.json();
      setSettings(data);
    } catch (error) {
      console.error('Error fetching settings:', error);
    }
  };

  const fetchDeliveryZones = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/delivery-zones`);
      const data = await response.json();
      setDeliveryZones(data);
    } catch (error) {
      console.error('Error fetching delivery zones:', error);
    }
  };

  const createOrder = async (orderData) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData)
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Order failed');
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error creating order:', error);
      throw error;
    }
  };

  // Cart Functions
  const addToCart = (product, size, quantity = 1) => {
    const cartItem = {
      id: `${product.id}-${size}`,
      product,
      size,
      quantity,
      price: product.selling_price
    };
    
    const existingItem = cart.find(item => item.id === cartItem.id);
    if (existingItem) {
      setCart(cart.map(item => 
        item.id === cartItem.id 
          ? { ...item, quantity: item.quantity + quantity }
          : item
      ));
    } else {
      setCart([...cart, cartItem]);
    }
  };

  const removeFromCart = (itemId) => setCart(cart.filter(item => item.id !== itemId));
  
  const updateCartQuantity = (itemId, newQuantity) => {
    if (newQuantity <= 0) {
      removeFromCart(itemId);
    } else {
      setCart(cart.map(item => 
        item.id === itemId ? { ...item, quantity: newQuantity } : item
      ));
    }
  };

  const getCartTotal = () => cart.reduce((total, item) => total + (item.price * item.quantity), 0);

  const toggleWishlist = (productId) => {
    if (wishlist.includes(productId)) {
      setWishlist(wishlist.filter(id => id !== productId));
    } else {
      setWishlist([...wishlist, productId]);
    }
  };

  const handleCheckout = async (customerData, deliveryZone) => {
    try {
      const orderData = {
        customer_name: customerData.name,
        customer_phone: customerData.phone,
        customer_email: customerData.email,
        delivery_address: customerData.address,
        delivery_zone: deliveryZone,
        customer_notes: customerData.notes || '',
        source: customerData.source === 'Prefer not to say' ? null : (customerData.source || 'Website'),
        items: cart.map(item => ({
          product_id: item.product.id,
          size: item.size,
          quantity: item.quantity
        }))
      };

      const result = await createOrder(orderData);
      
      if (result.whatsapp_url) {
        window.open(result.whatsapp_url, '_blank');
      }

      alert(`
🎉 Order Placed Successfully!

Order Number: ${result.order_number}
Total Amount: KES ${result.total_amount.toLocaleString()}

We’ve opened WhatsApp so you can confirm payment and delivery.
If it didn’t open, please contact us via WhatsApp.
      `);

      setCart([]);
      setView('store');
    } catch (error) {
      alert(`Order failed: ${error.message}`);
    }
  };

  // Helper Functions
  const getTotalStock = (product) => {
    if (!product.sizes) return 0;
    return product.sizes.reduce((sum, size) => sum + size.stock, 0);
  };


  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthNotice('');
    setAuthLoading(true);
    try {
      const passwordStrongEnough = (password) => {
        if (!password || password.length < 8) return false;
        const hasLetter = /[A-Za-z]/.test(password);
        const hasNumber = /\d/.test(password);
        return hasLetter && hasNumber;
      };
      if (authMode === 'register') {
        if (!passwordStrongEnough(authForm.password)) {
          setAuthError('Password must be at least 8 characters and include letters and numbers.');
          return;
        }
        if (authForm.password !== authForm.confirmPassword) {
          setAuthError('Passwords do not match.');
          return;
        }
        if (!authForm.phone.trim()) {
          setAuthError('Phone number is required.');
          return;
        }
        const payload = {
          name: authForm.name.trim(),
          email: authForm.email.trim(),
          phone: authForm.phone.trim(),
          password: authForm.password
        };
        const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
          setAuthError(data.detail || 'Registration failed.');
          return;
        }
        setAuthToken(data.token);
        setAuthKind('customer');
        try {
          localStorage.setItem('sn_auth_token', data.token);
          localStorage.setItem('sn_auth_kind', 'customer');
        } catch {}
        setAuthUser(data.user);
        setAuthOpen(false);
        setToastMessage('Account created successfully.');
        setAuthForm({
          name: '',
          email: '',
          phone: '',
          password: '',
          confirmPassword: '',
          resetToken: '',
          currentPassword: ''
        });
      } else if (authMode === 'login') {
        const payload = {
          email: authForm.email.trim(),
          password: authForm.password
        };
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
          setAuthError(data.detail || 'Authentication failed.');
          return;
        }
        setAuthToken(data.token);
        setAuthKind('customer');
        try {
          localStorage.setItem('sn_auth_token', data.token);
          localStorage.setItem('sn_auth_kind', 'customer');
        } catch {}
        setAuthUser(data.user);
        setAuthOpen(false);
        setToastMessage('Signed in successfully.');
        setAuthForm({
          name: '',
          email: '',
          phone: '',
          password: '',
          confirmPassword: '',
          resetToken: '',
          currentPassword: ''
        });
      } else if (authMode === 'forgot') {
        const payload = { identifier: authForm.email.trim() };
        const response = await fetch(`${API_BASE_URL}/api/auth/forgot-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
          setAuthError(data.detail || 'Request failed.');
          return;
        }
        setAuthNotice('If the account exists, reset instructions have been sent. Paste your reset token below.');
        setAuthMode('reset');
      } else if (authMode === 'reset') {
        if (!passwordStrongEnough(authForm.password)) {
          setAuthError('Password must be at least 8 characters and include letters and numbers.');
          return;
        }
        if (authForm.password !== authForm.confirmPassword) {
          setAuthError('Passwords do not match.');
          return;
        }
        const payload = {
          token: authForm.resetToken.trim(),
          new_password: authForm.password
        };
        const response = await fetch(`${API_BASE_URL}/api/auth/reset-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
          setAuthError(data.detail || 'Reset failed.');
          return;
        }
        setAuthNotice('Password reset successful. Please sign in.');
        setAuthMode('login');
        setAuthForm({
          name: '',
          email: '',
          phone: '',
          password: '',
          confirmPassword: '',
          resetToken: '',
          currentPassword: ''
        });
      } else if (authMode === 'change') {
        if (!passwordStrongEnough(authForm.password)) {
          setAuthError('Password must be at least 8 characters and include letters and numbers.');
          return;
        }
        if (authForm.password !== authForm.confirmPassword) {
          setAuthError('Passwords do not match.');
          return;
        }
        const payload = {
          current_password: authForm.currentPassword,
          new_password: authForm.password
        };
        const response = await fetch(`${API_BASE_URL}/api/auth/change-password`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authToken}`
          },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
          setAuthError(data.detail || 'Change password failed.');
          return;
        }
        setToastMessage('Password changed successfully.');
        setAuthMode('login');
        setAuthOpen(false);
        setAuthForm({
          name: '',
          email: '',
          phone: '',
          password: '',
          confirmPassword: '',
          resetToken: '',
          currentPassword: ''
        });
      } else if (authMode === 'staff') {
        const payload = {
          username: authForm.email.trim(),
          password: authForm.password
        };
        const response = await fetch(`${API_BASE_URL}/api/auth/staff/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
          setAuthError(data.detail || 'Staff login failed.');
          return;
        }
        setAuthToken(data.token);
        setAuthKind('staff');
        try {
          localStorage.setItem('sn_auth_token', data.token);
          localStorage.setItem('sn_auth_kind', 'staff');
        } catch {}
        setAuthUser({ ...data.staff, isStaff: true });
        setAuthOpen(false);
        setToastMessage('Staff login successful.');
        if (data.staff.role && data.staff.role.toLowerCase() !== 'admin') {
          window.location.href = POS_URL;
        }
      }

      if (postAuthView) {
        setView(postAuthView);
        setPostAuthView('');
      }
    } catch (error) {
      setAuthError('Something went wrong. Please try again.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    setAuthToken('');
    setAuthUser(null);
    setAuthKind('customer');
    try {
      localStorage.removeItem('sn_auth_token');
      localStorage.removeItem('sn_auth_kind');
    } catch {
      // ignore storage errors
    }
    setToastMessage('Signed out.');
  };

  const parseSizesInput = (value) => {
    if (!value) return [];
    return value
      .split(',')
      .map(entry => entry.trim())
      .filter(Boolean)
      .map(entry => {
        const [size, stock] = entry.split(':').map(part => part.trim());
        const quantity = Number(stock);
        return size && Number.isFinite(quantity) ? { size, stock: quantity } : null;
      })
      .filter(Boolean);
  };

  const handleAdminCreateProduct = async () => {
    setAdminError('');
    try {
      if (!adminProductForm.buying_price || !adminProductForm.selling_price) {
        setAdminError('Buying price and selling price are required.');
        return;
      }
      const sizes = parseSizesInput(adminProductForm.sizes);
      const payload = {
        category: adminProductForm.category,
        brand: adminProductForm.brand.trim(),
        model: adminProductForm.model.trim(),
        color: adminProductForm.color.trim(),
        image_url: adminProductForm.image_url.trim() || null,
        public_brand: adminProductForm.public_brand.trim() || null,
        public_title: adminProductForm.public_title.trim() || null,
        public_description: adminProductForm.public_description.trim() || null,
        buying_price: Number(adminProductForm.buying_price),
        selling_price: Number(adminProductForm.selling_price),
        sizes
      };
      if (Number.isNaN(payload.buying_price) || Number.isNaN(payload.selling_price)) {
        setAdminError('Buying price and selling price must be valid numbers.');
        return;
      }
      const response = await fetch(`${API_BASE_URL}/api/admin/products`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to create product.');
        return;
      }
      setToastMessage('Product created.');
        setAdminProductForm({
          category: 'Women',
          brand: '',
          model: '',
          color: '',
          image_url: '',
          public_brand: '',
          public_title: '',
          public_description: '',
          buying_price: '',
          selling_price: '',
          sizes: ''
        });
      const productsRes = await fetch(`${API_BASE_URL}/api/admin/products`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (productsRes.ok) {
        setAdminProducts(await productsRes.json());
      }
    } catch (error) {
      setAdminError('Failed to create product.');
    }
  };

  const handleAdminDeactivateProduct = async (productId) => {
    setAdminError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/products/${productId}/deactivate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (!response.ok) {
        const data = await response.json();
        setAdminError(data.detail || 'Failed to deactivate product.');
        return;
      }
      setToastMessage('Product deactivated.');
      setAdminProducts(adminProducts.map(p => p.id === productId ? { ...p, is_active: 0 } : p));
    } catch (error) {
      setAdminError('Failed to deactivate product.');
    }
  };

  const handleAdminActivateProduct = async (productId) => {
    setAdminError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/products/${productId}/activate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (!response.ok) {
        const data = await response.json();
        setAdminError(data.detail || 'Failed to activate product.');
        return;
      }
      setToastMessage('Product activated.');
      setAdminProducts(adminProducts.map(p => p.id === productId ? { ...p, is_active: 1 } : p));
    } catch (error) {
      setAdminError('Failed to activate product.');
    }
  };

  const openEditProduct = (product) => {
    setAdminEditProduct(product);
    const sizes = (product.sizes || [])
      .map(size => `${size.size}:${size.stock}`)
      .join(', ');
    setAdminEditForm({
      category: product.category || '',
      brand: product.brand || '',
      model: product.model || '',
      color: product.color || '',
      image_url: product.image_url || '',
      public_brand: product.public_brand || '',
      public_title: product.public_title || '',
      public_description: product.public_description || '',
      buying_price: product.buying_price ?? '',
      selling_price: product.selling_price ?? '',
      sizes
    });
  };

  const handleAdminUpdateProduct = async () => {
    if (!adminEditProduct) return;
    setAdminError('');
    try {
      const sizes = parseSizesInput(adminEditForm.sizes);
      const payload = {
        category: adminEditForm.category,
        brand: adminEditForm.brand,
        model: adminEditForm.model,
        color: adminEditForm.color,
        image_url: adminEditForm.image_url.trim() || null,
        public_brand: adminEditForm.public_brand.trim() || null,
        public_title: adminEditForm.public_title.trim() || null,
        public_description: adminEditForm.public_description.trim() || null,
        buying_price: adminEditForm.buying_price === '' ? null : Number(adminEditForm.buying_price),
        selling_price: adminEditForm.selling_price === '' ? null : Number(adminEditForm.selling_price),
        sizes
      };
      const response = await fetch(`${API_BASE_URL}/api/admin/products/${adminEditProduct.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to update product.');
        return;
      }
      setToastMessage('Product updated.');
      const productsRes = await fetch(`${API_BASE_URL}/api/admin/products`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (productsRes.ok) {
        setAdminProducts(await productsRes.json());
      }
      setAdminEditProduct(null);
    } catch (error) {
      setAdminError('Failed to update product.');
    }
  };

  const handleAdminImageUpload = async (file, target) => {
    if (!file) return;
    setAdminError('');
    setAdminUploadLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(`${API_BASE_URL}/api/admin/upload-image`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` },
        body: formData
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to upload image.');
        return;
      }
      if (target === 'edit') {
        setAdminEditForm({ ...adminEditForm, image_url: data.image_url || '' });
      } else if (target === 'blog') {
        setAdminBlogForm({ ...adminBlogForm, image_url: data.image_url || '' });
      } else if (target === 'blogEdit') {
        setAdminBlogForm({ ...adminBlogForm, image_url: data.image_url || '' });
      } else {
        setAdminProductForm({ ...adminProductForm, image_url: data.image_url || '' });
      }
      setToastMessage('Image uploaded.');
    } catch (error) {
      setAdminError('Failed to upload image.');
    } finally {
      setAdminUploadLoading(false);
    }
  };

  const handleAdminCreateBlog = async () => {
    setAdminError('');
    try {
      const payload = {
        title: adminBlogForm.title.trim(),
        category: adminBlogForm.category.trim(),
        excerpt: adminBlogForm.excerpt.trim(),
        content: adminBlogForm.content.trim(),
        image_url: adminBlogForm.image_url.trim() || null,
        is_published: adminBlogForm.is_published ? 1 : 0
      };
      const response = await fetch(`${API_BASE_URL}/api/admin/blog`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to create blog post.');
        return;
      }
      setToastMessage('Blog post created.');
      setAdminBlogForm({ title: '', category: '', excerpt: '', content: '', image_url: '', is_published: true });
      setAdminEditBlog(null);
      const blogRes = await fetch(`${API_BASE_URL}/api/admin/blog`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (blogRes.ok) {
        setAdminBlogPosts(await blogRes.json());
      }
    } catch (error) {
      setAdminError('Failed to create blog post.');
    }
  };

  const handleAdminUpdateBlog = async () => {
    if (!adminEditBlog) return;
    setAdminError('');
    try {
      const payload = {
        title: adminBlogForm.title.trim(),
        category: adminBlogForm.category.trim(),
        excerpt: adminBlogForm.excerpt.trim(),
        content: adminBlogForm.content.trim(),
        image_url: adminBlogForm.image_url.trim() || null,
        is_published: adminBlogForm.is_published ? 1 : 0
      };
      const response = await fetch(`${API_BASE_URL}/api/admin/blog/${adminEditBlog.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to update blog post.');
        return;
      }
      setToastMessage('Blog post updated.');
      const blogRes = await fetch(`${API_BASE_URL}/api/admin/blog`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (blogRes.ok) {
        setAdminBlogPosts(await blogRes.json());
      }
      setAdminEditBlog(null);
      setAdminBlogForm({ title: '', category: '', excerpt: '', content: '', image_url: '', is_published: true });
    } catch (error) {
      setAdminError('Failed to update blog post.');
    }
  };

  const handleAdminToggleBlog = async (postId) => {
    setAdminError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/blog/${postId}/toggle`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (!response.ok) {
        const data = await response.json();
        setAdminError(data.detail || 'Failed to update blog status.');
        return;
      }
      const blogRes = await fetch(`${API_BASE_URL}/api/admin/blog`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (blogRes.ok) {
        setAdminBlogPosts(await blogRes.json());
      }
    } catch (error) {
      setAdminError('Failed to update blog status.');
    }
  };

  const startEditBlog = (post) => {
    setAdminEditBlog(post);
    setAdminBlogForm({
      title: post.title || '',
      category: post.category || '',
      excerpt: post.excerpt || '',
      content: post.content || '',
      image_url: post.image_url || '',
      is_published: post.is_published ? true : false
    });
  };

  const startEditSection = (section) => {
    setAdminEditSection(section);
    setAdminSectionForm({
      title: section.title || '',
      category_label: section.category_label || '',
      category_match: section.category_match || '',
      model_keywords: section.model_keywords || '',
      filter_category: section.filter_category || 'All',
      filter_type: section.filter_type || 'All',
      limit_count: section.limit_count ?? '',
      alternate_brands: !!section.alternate_brands,
      allow_out_of_stock: !!section.allow_out_of_stock,
      sort_order: section.sort_order ?? 0,
      is_active: !!section.is_active
    });
  };

  const handleAdminCreateSection = async () => {
    setAdminError('');
    try {
      const payload = {
        title: adminSectionForm.title.trim(),
        category_label: adminSectionForm.category_label.trim() || null,
        category_match: adminSectionForm.category_match.trim() || null,
        model_keywords: adminSectionForm.model_keywords.trim() || null,
        filter_category: adminSectionForm.filter_category,
        filter_type: adminSectionForm.filter_type,
        limit_count: adminSectionForm.limit_count === '' ? null : Number(adminSectionForm.limit_count),
        alternate_brands: adminSectionForm.alternate_brands ? 1 : 0,
        allow_out_of_stock: adminSectionForm.allow_out_of_stock ? 1 : 0,
        sort_order: Number(adminSectionForm.sort_order) || 0,
        is_active: adminSectionForm.is_active ? 1 : 0
      };
      const response = await fetch(`${API_BASE_URL}/api/admin/sections`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to create section.');
        return;
      }
      setToastMessage('Section created.');
      setAdminSectionForm({
        title: '',
        category_label: '',
        category_match: '',
        model_keywords: '',
        filter_category: 'All',
        filter_type: 'All',
        limit_count: '',
        alternate_brands: false,
        allow_out_of_stock: false,
        sort_order: 0,
        is_active: true
      });
      const sectionsRes = await fetch(`${API_BASE_URL}/api/admin/sections`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (sectionsRes.ok) {
        setAdminSections(await sectionsRes.json());
      }
      const publicRes = await fetch(`${API_BASE_URL}/api/sections`);
      if (publicRes.ok) {
        const dataPublic = await publicRes.json();
        setHomeSections(Array.isArray(dataPublic) ? dataPublic : []);
      }
    } catch (error) {
      setAdminError('Failed to create section.');
    }
  };

  const handleAdminUpdateSection = async () => {
    if (!adminEditSection) return;
    setAdminError('');
    try {
      const payload = {
        title: adminSectionForm.title.trim(),
        category_label: adminSectionForm.category_label.trim() || null,
        category_match: adminSectionForm.category_match.trim() || null,
        model_keywords: adminSectionForm.model_keywords.trim() || null,
        filter_category: adminSectionForm.filter_category,
        filter_type: adminSectionForm.filter_type,
        limit_count: adminSectionForm.limit_count === '' ? null : Number(adminSectionForm.limit_count),
        alternate_brands: adminSectionForm.alternate_brands ? 1 : 0,
        allow_out_of_stock: adminSectionForm.allow_out_of_stock ? 1 : 0,
        sort_order: Number(adminSectionForm.sort_order) || 0,
        is_active: adminSectionForm.is_active ? 1 : 0
      };
      const response = await fetch(`${API_BASE_URL}/api/admin/sections/${adminEditSection.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to update section.');
        return;
      }
      setToastMessage('Section updated.');
      const sectionsRes = await fetch(`${API_BASE_URL}/api/admin/sections`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (sectionsRes.ok) {
        setAdminSections(await sectionsRes.json());
      }
      const publicRes = await fetch(`${API_BASE_URL}/api/sections`);
      if (publicRes.ok) {
        const dataPublic = await publicRes.json();
        setHomeSections(Array.isArray(dataPublic) ? dataPublic : []);
      }
      setAdminEditSection(null);
      setAdminSectionForm({
        title: '',
        category_label: '',
        category_match: '',
        model_keywords: '',
        filter_category: 'All',
        filter_type: 'All',
        limit_count: '',
        alternate_brands: false,
        allow_out_of_stock: false,
        sort_order: 0,
        is_active: true
      });
    } catch (error) {
      setAdminError('Failed to update section.');
    }
  };

  const handleAdminToggleSection = async (sectionId) => {
    setAdminError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/sections/${sectionId}/toggle`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (!response.ok) {
        const data = await response.json();
        setAdminError(data.detail || 'Failed to update section.');
        return;
      }
      const sectionsRes = await fetch(`${API_BASE_URL}/api/admin/sections`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (sectionsRes.ok) {
        setAdminSections(await sectionsRes.json());
      }
      const publicRes = await fetch(`${API_BASE_URL}/api/sections`);
      if (publicRes.ok) {
        const dataPublic = await publicRes.json();
        setHomeSections(Array.isArray(dataPublic) ? dataPublic : []);
      }
    } catch (error) {
      setAdminError('Failed to update section.');
    }
  };

  const handleAdminResetUserPassword = async () => {
    setAdminError('');
    try {
      const payload = {
        identifier: adminUserResetForm.identifier.trim(),
        new_password: adminUserResetForm.new_password
      };
      const response = await fetch(`${API_BASE_URL}/api/admin/users/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to reset user password.');
        return;
      }
      setToastMessage('User password reset.');
      setAdminUserResetForm({ identifier: '', new_password: '' });
      const usersRes = await fetch(`${API_BASE_URL}/api/admin/users?search=${encodeURIComponent(adminUserSearch)}`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (usersRes.ok) {
        setAdminUsers(await usersRes.json());
      }
    } catch (error) {
      setAdminError('Failed to reset user password.');
    }
  };

  const handleAdminSearchUsers = async () => {
    setAdminError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/users?search=${encodeURIComponent(adminUserSearch)}`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (!response.ok) {
        const data = await response.json();
        setAdminError(data.detail || 'Failed to load users.');
        return;
      }
      setAdminUsers(await response.json());
    } catch (error) {
      setAdminError('Failed to load users.');
    }
  };

  const handleAdminResetStaffPassword = async () => {
    setAdminError('');
    try {
      const payload = {
        username: adminStaffResetForm.username.trim(),
        new_password: adminStaffResetForm.new_password
      };
      const response = await fetch(`${API_BASE_URL}/api/admin/staff/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to reset staff password.');
        return;
      }
      setToastMessage('Staff password reset.');
      setAdminStaffResetForm({ username: '', new_password: '' });
      const staffRes = await fetch(`${API_BASE_URL}/api/admin/staff`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (staffRes.ok) {
        setAdminStaff(await staffRes.json());
      }
    } catch (error) {
      setAdminError('Failed to reset staff password.');
    }
  };
  const handleAdminCreateStaff = async () => {
    setAdminError('');
    if (!adminStaffForm.username.trim() || !adminStaffForm.password.trim()) {
      setAdminError('Username and password are required.');
      return;
    }
    try {
      const payload = {
        username: adminStaffForm.username.trim(),
        password: adminStaffForm.password,
        role: adminStaffForm.role
      };
      const response = await fetch(`${API_BASE_URL}/api/admin/staff`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to create staff user.');
        return;
      }
      setToastMessage('Staff user created.');
      setAdminStaffForm({ username: '', password: '', role: 'Cashier' });
      const staffRes = await fetch(`${API_BASE_URL}/api/admin/staff`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (staffRes.ok) {
        setAdminStaff(await staffRes.json());
      }
      setAdminEditingStaff(null);
    } catch (error) {
      setAdminError('Failed to create staff user.');
    }
  };

  const startEditStaff = (staff) => {
    setAdminEditingStaff(staff);
    setAdminStaffForm({
      username: staff.username || '',
      password: '',
      role: staff.role || 'Cashier'
    });
  };

  const cancelEditStaff = () => {
    setAdminEditingStaff(null);
    setAdminStaffForm({ username: '', password: '', role: 'Cashier' });
  };

  const handleAdminUpdateStaff = async (staffId) => {
    setAdminError('');
    if (!adminStaffForm.password.trim()) {
      setAdminError('Password is required to update staff.');
      return;
    }
    try {
      const payload = {
        username: adminStaffForm.username.trim(),
        password: adminStaffForm.password,
        role: adminStaffForm.role
      };
      const response = await fetch(`${API_BASE_URL}/api/admin/staff/${staffId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to update staff user.');
        return;
      }
      setToastMessage('Staff user updated.');
      const staffRes = await fetch(`${API_BASE_URL}/api/admin/staff`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (staffRes.ok) {
        setAdminStaff(await staffRes.json());
      }
      setAdminEditingStaff(null);
    } catch (error) {
      setAdminError('Failed to update staff user.');
    }
  };

  const handleAdminDeactivateStaff = async (staffId) => {
    setAdminError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/staff/${staffId}/deactivate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (!response.ok) {
        const data = await response.json();
        setAdminError(data.detail || 'Failed to deactivate staff.');
        return;
      }
      setToastMessage('Staff deactivated.');
      setAdminStaff(adminStaff.map(s => s.id === staffId ? { ...s, is_active: 0 } : s));
    } catch (error) {
      setAdminError('Failed to deactivate staff.');
    }
  };

  const handleAdminActivateStaff = async (staffId) => {
    setAdminError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/staff/${staffId}/activate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (!response.ok) {
        const data = await response.json();
        setAdminError(data.detail || 'Failed to activate staff.');
        return;
      }
      setToastMessage('Staff activated.');
      setAdminStaff(adminStaff.map(s => s.id === staffId ? { ...s, is_active: 1 } : s));
    } catch (error) {
      setAdminError('Failed to activate staff.');
    }
  };

  const pickFeaturedProducts = () => {
    const inStock = products.filter(p => getTotalStock(p) > 0);
    if (inStock.length === 0) return [];

    const picks = [];
    const used = new Set();

    const normalize = (value) => (value || '').toLowerCase();
    const brandOf = (p) => normalize(p.brand);

    const slotRules = [
      {
        label: 'Zara Preferred',
        match: (p) => {
          const brand = brandOf(p);
          if (!brand.includes('zara')) return false;
          const model = normalize(p.model);
          const color = normalize(p.color);
          return model.includes('white') || color.includes('white') || model.includes('suede brown') || color.includes('suede brown');
        },
        fallback: (p) => brandOf(p).includes('zara')
      },
      {
        label: 'EGO Heel',
        match: (p) => brandOf(p).includes('ego') && normalize(p.category).includes('heel')
      },
      {
        label: 'Men Hermes',
        match: (p) => brandOf(p).includes('hermes') && normalize(p.category).includes('men')
      },
      {
        label: 'Primark White',
        match: (p) => {
          if (!brandOf(p).includes('primark')) return false;
          const model = normalize(p.model);
          const color = normalize(p.color);
          return model.includes('white') || color.includes('white') || model.includes('brown') || color.includes('brown') || model.includes('beige') || color.includes('beige') || model.includes('black') || color.includes('black');
        }
      },
      {
        label: 'Erynn-Paris',
        match: (p) => {
          const brand = brandOf(p);
          if (brand !== 'erynn paris') return false;
          const model = normalize(p.model);
          const color = normalize(p.color);
          return model.includes('pink-orange') || color.includes('pink-orange') || model.includes('pink') || color.includes('pink') || model.includes('orange') || color.includes('orange') || model.includes('brown') || color.includes('brown');
        }
      },
      {
        label: 'Doll Shoes',
        match: (p) => {
          const category = normalize(p.category);
          if (!category.includes('doll') && !category.includes('flat')) return false;
          const model = normalize(p.model);
          const color = normalize(p.color);
          return model.includes('denim-black') || color.includes('denim-black') || model.includes('denim') || color.includes('denim') || model.includes('black') || color.includes('black') || model.includes('animal print') || color.includes('animal print');
        }
      },
      {
        label: 'JM Slides Black',
        match: (p) => {
          if (!brandOf(p).includes('jm')) return false;
          const category = normalize(p.category);
          if (!category.includes('slides')) return false;
          const model = normalize(p.model);
          const color = normalize(p.color);
          return model.includes('black') || color.includes('black') || model.includes('grey') || color.includes('grey') || model.includes('gray') || color.includes('gray');
        }
      },
      {
        label: 'Primark Beige',
        match: (p) => {
          if (!brandOf(p).includes('primark')) return false;
          const model = normalize(p.model);
          const color = normalize(p.color);
          return model.includes('beige') || color.includes('beige') || model.includes('white') || color.includes('white') || model.includes('black') || color.includes('black');
        }
      }
    ];

    const pickFromMatches = (matches, offset, lastBrand) => {
      if (matches.length === 0) return null;
      const startIndex = offset % matches.length;
      for (let i = 0; i < matches.length; i++) {
        const candidate = matches[(startIndex + i) % matches.length];
        if (used.has(candidate.id)) continue;
        if (lastBrand && brandOf(candidate) === lastBrand) continue;
        return candidate;
      }
      for (let i = 0; i < matches.length; i++) {
        const candidate = matches[(startIndex + i) % matches.length];
        if (!used.has(candidate.id)) return candidate;
      }
      return null;
    };

    slotRules.forEach((slot, slotIndex) => {
      const primaryMatches = inStock.filter(slot.match);
      const fallbackMatches = slot.fallback ? inStock.filter(slot.fallback) : [];
      const pool = primaryMatches.length > 0 ? primaryMatches : fallbackMatches;
      if (pool.length === 0) return;
      const lastBrand = picks.length > 0 ? brandOf(picks[picks.length - 1]) : null;
      const picked = pickFromMatches(pool, featuredHourKey + slotIndex, lastBrand);
      if (picked) {
        picks.push(picked);
        used.add(picked.id);
      }
    });

    if (picks.length < 8) {
      const remainder = inStock.filter(p => !used.has(p.id));
      const startIndex = featuredHourKey % (remainder.length || 1);
      for (let i = 0; i < remainder.length && picks.length < 8; i++) {
        const candidate = remainder[(startIndex + i) % remainder.length];
        const lastBrand = picks.length > 0 ? brandOf(picks[picks.length - 1]) : null;
        if (lastBrand && brandOf(candidate) === lastBrand) continue;
        picks.push(candidate);
        used.add(candidate.id);
      }
      // If brand-avoidance blocked all remaining, fill with any leftover
      if (picks.length < 8) {
        for (let i = 0; i < remainder.length && picks.length < 8; i++) {
          const candidate = remainder[(startIndex + i) % remainder.length];
          if (used.has(candidate.id)) continue;
          picks.push(candidate);
          used.add(candidate.id);
        }
      }
    }

  return picks.slice(0, 8);
  };

  const handleAdminUpdateOrderStatus = async (orderId, status, paymentStatus, paymentMethod) => {
    setAdminError('');
    try {
      const payload = {
        status,
        payment_status: paymentStatus,
        payment_method: paymentMethod || null,
        paid_at: paymentStatus === 'PAID' ? new Date().toISOString() : null
      };
      const response = await fetch(`${API_BASE_URL}/api/admin/orders/${orderId}/status`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to update order.');
        return;
      }
      setToastMessage('Order updated.');
      const ordersRes = await fetch(`${API_BASE_URL}/api/admin/orders`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (ordersRes.ok) {
        setAdminOrders(await ordersRes.json());
      }
    } catch (error) {
      setAdminError('Failed to update order.');
    }
  };

  async function handleAdminRegeneratePublic() {
    setAdminError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/products/regenerate-public?overwrite=true`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` }
      });
      const data = await response.json();
      if (!response.ok) {
        setAdminError(data.detail || 'Failed to regenerate public titles.');
        return;
      }
      setToastMessage(`Regenerated ${data.updated || 0} products.`);
      const productsRes = await fetch(`${API_BASE_URL}/api/admin/products`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (productsRes.ok) {
        setAdminProducts(await productsRes.json());
      }
    } catch (error) {
      setAdminError('Failed to regenerate public titles.');
    }
  }

  const getAdminSourceBreakdown = () => {
    const counts = {};
    adminOrders.forEach(order => {
      const source = (order.source && order.source.trim()) || 'Unknown';
      counts[source] = (counts[source] || 0) + 1;
    });
    const total = adminOrders.length;
    const rows = Object.keys(counts)
      .sort((a, b) => counts[b] - counts[a])
      .map(source => ({
        source,
        count: counts[source],
        percent: total > 0 ? Math.round((counts[source] / total) * 100) : 0
      }));
    return { total, rows };
  };

  // Product Card Component
  const renderProductCard = (product) => {
    const totalStock = getTotalStock(product);
    const isInWishlist = wishlist.includes(product.id);
    const imageUrl = `${API_BASE_URL}${product.image_url}`;
    
    return (
      <div key={product.id} className="group bg-white rounded-xl overflow-hidden shadow-md hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-1 cursor-pointer relative">
        <div onClick={() => { setSelectedProduct(product); setView('product'); }} className="relative aspect-square overflow-hidden bg-gray-100">
          <img 
            src={imageUrl} 
            alt={`${getPublicTitle(product)} - ${product.color}`}
            className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
            onError={(e) => { e.target.src = '/api/placeholder/400/400'; }}
          />
          
          {totalStock < 10 && totalStock > 0 && (
            <div className="absolute top-3 left-3 bg-orange-500 text-white text-xs px-3 py-1 rounded-full font-semibold animate-pulse">
              LEAVING SOON
            </div>
          )}

          <button 
            onClick={(e) => { e.stopPropagation(); toggleWishlist(product.id); }}
            className={`absolute top-3 right-3 rounded-full p-2 transition-all shadow-lg ${
              isInWishlist ? 'bg-red-600 text-white' : 'bg-white text-gray-600 opacity-0 group-hover:opacity-100'
            }`}
          >
            <Heart size={18} className={isInWishlist ? 'fill-current' : ''} />
          </button>

          {totalStock < 10 && totalStock > 0 && (
            <div className="absolute bottom-3 right-3 bg-yellow-500 text-black text-xs px-3 py-1 rounded-full font-semibold">
              Only {totalStock} left
            </div>
          )}

          {totalStock === 0 && (
            <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
              <span className="bg-white text-black px-4 py-2 rounded-lg font-bold">SOLD OUT</span>
            </div>
          )}
        </div>

        <div onClick={() => { setSelectedProduct(product); setView('product'); }} className="p-4">
          <div className="text-xs text-gray-500 uppercase mb-1 font-semibold">{getPublicBrand(product)}</div>
          <h3 className="font-bold text-lg mb-1 group-hover:text-red-600 transition">{getPublicTitle(product)}</h3>
          <div className="text-sm text-gray-600 mb-3">{product.color} • {product.category}</div>
          <div className="text-xl font-bold text-red-600">KES {product.selling_price.toLocaleString()}</div>
        </div>
      </div>
    );
  };

  // Featured/Trending Products Section
  const FeaturedSection = () => {
    const featuredProducts = pickFeaturedProducts();
    if (featuredProducts.length === 0) return null;

    return (
      <div className="bg-gray-50 py-12">
        <div className="container mx-auto px-4">
          <div className="text-center mb-8">
            <div className="inline-flex items-center space-x-2 bg-red-600 text-white px-4 py-2 rounded-full mb-3">
              <TrendingUp size={20} />
              <span className="font-bold">SANDALS TRENDING NOW</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold mb-2">🔥 Hot Slides Sandals Heels Sneakers Shoes Now</h2>
            <p className="text-gray-600">Most popular footwear styles flying off the shelves in Nairobi</p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {featuredProducts.map(product => {
              const imageUrl = `${API_BASE_URL}${product.image_url}`;
              const totalStock = getTotalStock(product);
              
              return (
                <div 
                  key={product.id}
                  className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-xl transition-all cursor-pointer transform hover:-translate-y-1"
                  onClick={() => { setSelectedProduct(product); setView('product'); }}
                >
                  <div className="relative aspect-square overflow-hidden bg-gray-100">
                    <img
                      src={imageUrl}
                    alt={`${getPublicTitle(product)}`}
                      className="w-full h-full object-cover hover:scale-105 transition-transform duration-300"
                      onError={(e) => { e.target.src = '/api/placeholder/400/400'; }}
                    />
                    <div className="absolute top-2 left-2 bg-red-600 text-white text-xs px-2 py-1 rounded-full font-semibold flex items-center space-x-1">
                      <span>🔥</span>
                      <span>TRENDING</span>
                    </div>
                    {totalStock < 10 && (
                      <div className="absolute bottom-2 right-2 bg-orange-500 text-white text-xs px-2 py-1 rounded-full font-semibold">
                        {totalStock} left
                      </div>
                    )}
                  </div>
                  <div className="p-3">
                    <div className="text-xs text-gray-500 uppercase mb-1">{getPublicBrand(product)}</div>
                    <h3 className="font-semibold text-sm mb-1 truncate">{getPublicTitle(product)}</h3>
                    <p className="text-xs text-gray-600 mb-2 truncate">{product.color}</p>
                    <p className="text-lg font-bold text-red-600">KES {product.selling_price?.toLocaleString()}</p>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="text-center mt-8">
              <button 
                onClick={() => { setView('store'); setFilterCategory('All'); setFilterType('All'); }}
                className="bg-black hover:bg-red-600 text-white px-8 py-3 rounded-lg font-semibold transition inline-flex items-center space-x-2"
              >
                <span>View All Products</span>
                <ArrowRight size={18} />
              </button>
          </div>
        </div>
      </div>
    );
  };

  const CategorySection = ({ title, matchCategory, filterCategoryLabel = 'All', filterTypeLabel = 'All', showWhenEmpty = false, exactProductNames = [], fallbackKeywords = [], categoryLabelMatch = '', modelKeywords = [], allowOutOfStock = false, prioritizeBrands = [], prioritizeKeywords = [], limit = 8, alternateBrands = false }) => {
    const items = products.filter(p => {
      const category = (p.category || '').toLowerCase();
      const categoryTokens = category.split(/[^a-z0-9]+/).filter(Boolean);
      const inStock = getTotalStock(p) > 0;
      if (!allowOutOfStock && !inStock) return false;
      if (categoryLabelMatch) {
        const label = categoryLabelMatch.toLowerCase();
        if (!categoryTokens.includes(label)) return false;
        if (modelKeywords.length > 0) {
          const model = (p.model || '').toLowerCase();
          const categoryText = (p.category || '').toLowerCase();
          const haystack = `${model} ${categoryText}`;
          const hasKeyword = modelKeywords.some(keyword => haystack.includes(keyword.toLowerCase()));
          if (!hasKeyword) return false;
        }
        return true;
      }
      if (exactProductNames.length > 0) {
        const normalizeKey = (value) => (value || '').toLowerCase().replace(/[\s_]+/g, '-');
        const modelKey = normalizeKey(p.model);
        const imageKey = normalizeKey((p.image_url || '').split('/').pop());
        return exactProductNames.some(name => {
          const key = normalizeKey(name);
          return modelKey.includes(key) || imageKey.includes(key);
        });
      }
      return category.includes(matchCategory);
    });

    const normalizedPrioritizeBrands = prioritizeBrands.map(b => b.toLowerCase());
    const normalizedPrioritizeKeywords = prioritizeKeywords.map(k => k.toLowerCase());
    const scoredItems = items.map((p) => {
      const brand = (p.brand || '').toLowerCase();
      const model = (p.model || '').toLowerCase();
      let score = 0;
      if (normalizedPrioritizeBrands.includes(brand)) score += 2;
      if (normalizedPrioritizeKeywords.some(k => model.includes(k))) score += 1;
      return { product: p, score };
    });

    const scoredSortedItems = scoredItems
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return (a.product.id || 0) - (b.product.id || 0);
      })
      .map(entry => entry.product);

    const buildAlternatingBrandList = (list) => {
      if (!alternateBrands) return list;
      const brandBuckets = new Map();
      list.forEach(item => {
        const brand = (item.brand || 'Unknown').toLowerCase();
        if (!brandBuckets.has(brand)) brandBuckets.set(brand, []);
        brandBuckets.get(brand).push(item);
      });
      const brands = Array.from(brandBuckets.keys());
      const result = [];
      let index = 0;
      while (brands.length > 0) {
        const brand = brands[index % brands.length];
        const bucket = brandBuckets.get(brand);
        if (bucket && bucket.length > 0) {
          result.push(bucket.shift());
        }
        if (!bucket || bucket.length === 0) {
          brandBuckets.delete(brand);
          brands.splice(index % brands.length, 1);
          if (brands.length === 0) break;
          index = index % brands.length;
          continue;
        }
        index += 1;
      }
      return result;
    };

    const sortedItems = buildAlternatingBrandList(scoredSortedItems);
    const limitedItems = typeof limit === 'number' ? sortedItems.slice(0, limit) : sortedItems;

    const fallbackItems = limitedItems.length === 0 && fallbackKeywords.length > 0
      ? products.filter(p => {
          if (getTotalStock(p) <= 0) return false;
          const haystack = [
            p.brand,
            p.model,
            p.color,
            p.category
          ].join(' ').toLowerCase();
          return fallbackKeywords.every(keyword => haystack.includes(keyword));
        }).slice(0, 8)
      : [];

    const finalItems = limitedItems.length > 0 ? limitedItems : fallbackItems;

    if (finalItems.length === 0 && !showWhenEmpty) return null;

    return (
      <section className="container mx-auto px-4 py-10 sm:py-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl sm:text-3xl font-bold">{title}</h2>
          <button
            onClick={() => { 
              setView('store'); 
              setFilterCategory(filterCategoryLabel); 
              setFilterType(filterTypeLabel); 
            }}
            className="text-sm font-semibold text-red-600 hover:underline"
          >
            Browse more
          </button>
        </div>
        {finalItems.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-6 text-center text-sm text-gray-500">
            Products coming soon.
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
            {finalItems.map(product => renderProductCard(product))}
          </div>
        )}
      </section>
    );
  };

  // Floating Sale Button
  const FloatingSaleButton = () => {
    if (!showSaleButton) return null;

    return (
      <div className="fixed bottom-24 right-6 z-40 animate-bounce">
        <button
          onClick={() => {
            setFilterCategory('All');
            setFilterType('All');
            setView('store');
            setTimeout(() => {
              const productsSection = document.getElementById('products-section');
              if (productsSection) {
                productsSection.scrollIntoView({ behavior: 'smooth' });
              }
            }, 100);
          }}
          className="bg-gradient-to-r from-red-600 to-pink-600 text-white px-6 py-3 rounded-full shadow-2xl hover:shadow-3xl transition-all flex items-center gap-2 font-bold text-sm transform hover:scale-105"
        >
          <span className="text-xl">🎉</span>
          <span>SHOP SALE</span>
          <span className="text-xl">🎉</span>
        </button>
        
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowSaleButton(false);
          }}
          className="absolute -top-2 -right-2 bg-black text-white rounded-full w-6 h-6 flex items-center justify-center text-xs hover:bg-gray-800 transition"
        >
          ×
        </button>
      </div>
    );
  };

  if (authUser?.isStaff && authUser?.role && authUser.role.toLowerCase() !== 'admin') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="bg-white rounded-xl p-6 shadow-md max-w-md text-center">
          <h1 className="text-2xl font-bold mb-2">POS Access Only</h1>
          <p className="text-gray-600 mb-6">
            Your account is for staff POS access. Please use the POS dashboard.
          </p>
          <div className="flex flex-col gap-3">
            <a
              href={POS_URL}
              className="bg-black hover:bg-red-600 text-white px-6 py-3 rounded-lg font-semibold transition"
            >
              Open POS
            </a>
            <button
              onClick={handleLogout}
              className="border-2 border-gray-200 hover:border-black px-6 py-3 rounded-lg font-semibold transition"
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      {toastMessage && (
        <div className="fixed top-4 right-4 z-50 bg-black text-white px-4 py-2 rounded-lg shadow-lg text-sm">
          {toastMessage}
        </div>
      )}
      {/* Announcement Bar */}
      <div className="bg-red-600 text-white py-1 px-4 text-center text-[10px] sm:text-xs font-semibold tracking-wide overflow-hidden">
        <div className="animate-marquee whitespace-nowrap inline-block">
          🔒 AUTHENTICITY GUARANTEED · SAME-DAY DELIVERY NAIROBI · JOIN 50,000+ HAPPY CUSTOMERS · FREE SHIPPING OVER KES 10,000
        </div>
      </div>

      {/* Header - Compact & Clean */}
      <header className="sticky top-0 z-50 bg-black text-white shadow-lg">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-[6rem]">
            {/* Logo - With Image Support */}
            <button onClick={() => setView('store')} className="flex items-center space-x-2 hover:opacity-80 transition">
              <img 
                src="/shoes-nexus-logo.png" 
                alt="Shoes Nexus Kenya" 
                className="h-[5.85rem] w-auto object-contain"
                onError={(e) => { 
                  e.target.style.display = 'none';
                  e.target.nextElementSibling.style.display = 'block';
                }}
              />
              <div style={{display: 'block'}}>
                <div className="font-bold text-sm sm:text-base leading-none">SHOES NEXUS</div>
                <div className="text-[10px] text-gray-400 hidden sm:block">Discover Your Perfect Pair</div>
              </div>
            </button>

            {/* Desktop Navigation */}
            <nav className="hidden lg:flex items-center space-x-3">
              <button onClick={() => { setView('store'); setFilterCategory('All'); setFilterType('All'); }} className="px-2.5 py-1 rounded-md hover:bg-red-600 hover:text-white transition font-medium text-xs">Shop All</button>
              <button onClick={() => { setView('store'); setFilterCategory('Women'); setFilterType('All'); }} className="px-2.5 py-1 rounded-md hover:bg-red-600 hover:text-white transition font-medium text-xs">Women</button>
              <button onClick={() => { setView('store'); setFilterCategory('Men'); setFilterType('All'); }} className="px-2.5 py-1 rounded-md hover:bg-red-600 hover:text-white transition font-medium text-xs">Men</button>
              <div className="relative">
                <button 
                  onClick={() => setSandalsMenuOpen(prev => !prev)}
                  className="px-2.5 py-1 rounded-md hover:bg-red-600 hover:text-white transition font-medium text-xs"
                >
                  Sandals and Slides
                </button>
                {sandalsMenuOpen && (
                  <div className="absolute left-0 mt-2 w-40 bg-black text-white rounded-lg shadow-xl border border-gray-800 p-2 z-50">
                    <button
                      onClick={() => { 
                        setView('store'); 
                        setFilterCategory('Women'); 
                        setFilterType('Sandals'); 
                        setSandalsMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 rounded-md hover:bg-red-600 transition text-xs"
                    >
                      Women
                    </button>
                    <button
                      onClick={() => { 
                        setView('store'); 
                        setFilterCategory('Men'); 
                        setFilterType('Sandals'); 
                        setSandalsMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 rounded-md hover:bg-red-600 transition text-xs"
                    >
                      Men
                    </button>
                  </div>
                )}
              </div>
              <button onClick={() => { setView('store'); setFilterCategory('All'); setFilterType('Sneakers'); }} className="px-2.5 py-1 rounded-md hover:bg-red-600 hover:text-white transition font-medium text-xs">Sneakers</button>
              <button onClick={() => { setView('store'); setFilterCategory('All'); setFilterType('Heels'); }} className="px-2.5 py-1 rounded-md hover:bg-red-600 hover:text-white transition font-medium text-xs">Heels</button>
              <button onClick={() => { setView('store'); setFilterCategory('All'); setFilterType('Accessories'); }} className="px-2.5 py-1 rounded-md hover:bg-red-600 hover:text-white transition font-medium text-xs">Accessories</button>
            </nav>

            {/* Action Buttons */}
            <div className="flex items-center space-x-3 sm:space-x-4">
              <div className="relative group hidden sm:block">
                <Search size={20} className="cursor-pointer" />
                <div className="absolute top-full right-0 mt-2 w-64 bg-white text-black rounded-lg shadow-xl p-4 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all">
                  <input 
                    type="text"
                    placeholder="Search products..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full border-2 border-gray-200 rounded-lg px-3 py-2 focus:border-red-600 outline-none text-sm"
                  />
                </div>
              </div>
              <button onClick={() => setView('wishlist')} className="hover:text-red-500 transition relative">
                <Heart size={20} />
                {wishlist.length > 0 && <span className="absolute -top-2 -right-2 bg-red-600 text-white text-xs w-5 h-5 rounded-full flex items-center justify-center">{wishlist.length}</span>}
              </button>
              <button
                onClick={() => {
                  if (authUser) {
                    setView('account');
                  } else {
                    setAuthOpen(true);
                    setAuthMode('login');
                  }
                }}
                className="hover:text-red-500 transition hidden sm:block"
                title={authUser ? 'My Account' : 'Sign in'}
              >
                <User size={20} />
              </button>
              <button onClick={() => setView('cart')} className="relative hover:text-red-500 transition">
                <ShoppingCart size={20} />
                {cart.length > 0 && <span className="absolute -top-2 -right-2 bg-red-600 text-white text-xs w-5 h-5 rounded-full flex items-center justify-center font-bold">{cart.length}</span>}
              </button>
              <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="lg:hidden">
                {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
              </button>
            </div>
          </div>

          {/* Mobile Menu */}
          {mobileMenuOpen && (
            <div className="lg:hidden py-4 border-t border-gray-800 space-y-3">
              <input 
                type="text"
                placeholder="Search products..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full border-2 border-gray-700 bg-gray-900 text-white rounded-lg px-3 py-2 focus:border-red-600 outline-none text-sm mb-3"
              />
              <button onClick={() => { setView('store'); setFilterCategory('Women'); setFilterType('All'); setMobileMenuOpen(false); }} className="block w-full text-left hover:text-red-500 transition py-2">Women</button>
              <button onClick={() => { setView('store'); setFilterCategory('Men'); setFilterType('All'); setMobileMenuOpen(false); }} className="block w-full text-left hover:text-red-500 transition py-2">Men</button>
              <div className="pt-1 text-xs uppercase tracking-wider text-gray-400">Sandals and Slides</div>
              <button onClick={() => { setView('store'); setFilterCategory('Women'); setFilterType('Sandals'); setMobileMenuOpen(false); }} className="block w-full text-left hover:text-red-500 transition py-2">Women</button>
              <button onClick={() => { setView('store'); setFilterCategory('Men'); setFilterType('Sandals'); setMobileMenuOpen(false); }} className="block w-full text-left hover:text-red-500 transition py-2">Men</button>
              <button onClick={() => { setView('store'); setFilterCategory('All'); setFilterType('Sneakers'); setMobileMenuOpen(false); }} className="block w-full text-left hover:text-red-500 transition py-2">Sneakers</button>
            </div>
          )}
        </div>
      </header>

      {/* Main Content */}
      {view === 'store' && (
        <>
          {/* Hero - Slim Band */}
          <section className="relative bg-gradient-to-br from-black via-gray-900 to-red-900 text-white py-4 sm:py-6 overflow-hidden">
            <div className="absolute inset-0 opacity-10">
              <div className="absolute top-10 left-10 w-64 h-64 bg-red-500 rounded-full filter blur-3xl animate-pulse"></div>
              <div className="absolute bottom-10 right-10 w-96 h-96 bg-white rounded-full filter blur-3xl animate-pulse"></div>
            </div>
            
            <div className="container mx-auto px-4 relative z-10">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                <div className="max-w-3xl">
                  <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold leading-tight">
                    Discover Your <span className="text-red-500">Perfect Pair</span>
                  </h1>
                  <p className="text-xs sm:text-sm text-gray-300 mt-2">
                    Stylish Sneakers • Classy Sandals • High Heels • Boots • Flat Shoes • And More for ALL
                  </p>
                </div>
                <div className="flex flex-wrap gap-3 lg:justify-end">
                  <button 
                    onClick={() => setFilterCategory('Women')}
                    className="bg-red-600 hover:bg-red-700 text-white px-5 py-2.5 rounded-lg font-semibold transition-all transform hover:scale-105 flex items-center space-x-2 text-sm"
                  >
                    <span>Shop Women</span>
                    <ArrowRight size={16} />
                  </button>
                  <button 
                    onClick={() => setFilterCategory('Men')}
                    className="bg-white text-black hover:bg-gray-100 px-5 py-2.5 rounded-lg font-semibold transition-all transform hover:scale-105 text-sm"
                  >
                    Shop Men
                  </button>
                </div>
              </div>
            </div>
          </section>

          {/* Featured/Trending Section */}
          {!loading && products.length > 0 && <FeaturedSection />}

          {!loading && products.length > 0 && (
            <>
              {homeSections.map(section => (
                <CategorySection
                  key={section.id}
                  title={section.title}
                  matchCategory={section.category_match || ''}
                  categoryLabelMatch={section.category_label || ''}
                  modelKeywords={(section.model_keywords || '').split(',').map(k => k.trim()).filter(Boolean)}
                  filterCategoryLabel={section.filter_category || 'All'}
                  filterTypeLabel={section.filter_type || 'All'}
                  allowOutOfStock={!!section.allow_out_of_stock}
                  alternateBrands={!!section.alternate_brands}
                  limit={typeof section.limit_count === 'number' ? section.limit_count : (section.limit_count === null ? null : (section.limit_count === '' ? null : Number(section.limit_count)))}
                />
              ))}
              <CategorySection 
                title="Women Flat Sandals"
                matchCategory="women sandals"
                categoryLabelMatch="women"
                modelKeywords={['sandal', 'strap', 'new 3-strap', '3-strap', 'multistrap', 'multi-strap', 'new design', 'diamond strap', 'metal strap']}
                filterCategoryLabel="Women"
                filterTypeLabel="Sandals"
                allowOutOfStock={true}
                alternateBrands={true}
                limit={null}
              />
              <CategorySection 
                title="Women Slides"
                matchCategory="women slides"
                categoryLabelMatch="women"
                modelKeywords={['slide']}
                filterCategoryLabel="Women"
                filterTypeLabel="Sandals"
              />
            </>
          )}

          {/* Products Section */}
          <section id="products-section" className="container mx-auto px-4 py-12 sm:py-16">
            <h2 className="text-2xl sm:text-3xl font-bold mb-6 sm:mb-8">
              {filterCategory === 'All' ? 'All Products' : `${filterCategory}'s Shoes`}
            </h2>

            {loading ? (
              <div className="flex justify-center items-center py-20">
                <Loader className="animate-spin text-red-600" size={48} />
              </div>
            ) : products.length === 0 ? (
              <div className="text-center py-20">
                <p className="text-gray-500 text-xl">No products found</p>
                <button 
                  onClick={() => { setFilterCategory('All'); setSearchQuery(''); }}
                  className="mt-4 text-red-600 hover:underline"
                >
                  Clear filters
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
                {products.map(product => renderProductCard(product))}
              </div>
            )}
          </section>
        </>
      )}

      {/* Product Detail, Cart, Checkout, Wishlist Views remain the same */}
      {view === 'product' && selectedProduct && (
        <div className="container mx-auto px-4 py-12">
          <button 
            onClick={() => setView('store')}
            className="mb-8 text-gray-600 hover:text-black transition flex items-center space-x-2"
          >
            <span>←</span>
            <span>Back to Shop</span>
          </button>

          <div className="grid md:grid-cols-2 gap-12">
            <div className="aspect-square bg-gray-100 rounded-2xl overflow-hidden sticky top-24">
              <img 
                src={`${API_BASE_URL}${selectedProduct.image_url}`}
                alt={`${getPublicTitle(selectedProduct)}`}
                className="w-full h-full object-cover"
                onError={(e) => { e.target.src = '/api/placeholder/600/600'; }}
              />
            </div>

            <div className="space-y-6">
              <div>
                <div className="text-sm text-gray-500 uppercase mb-2 font-semibold">{getPublicBrand(selectedProduct)}</div>
                <h1 className="text-4xl font-bold mb-3">{getPublicTitle(selectedProduct)}</h1>
                {getPublicDescription(selectedProduct) && (
                  <p className="text-gray-600 mb-3">{getPublicDescription(selectedProduct)}</p>
                )}
                <div className="flex items-center space-x-4 text-gray-600 mb-4">
                  <span>{selectedProduct.color}</span>
                  <span>•</span>
                  <span>{selectedProduct.category}</span>
                </div>
                <div className="text-3xl font-bold text-red-600 mb-6">
                  KES {selectedProduct.selling_price.toLocaleString()}
                </div>
              </div>

              <div>
                <label className="font-semibold text-lg mb-3 block">Select Size</label>
                <div className="grid grid-cols-6 gap-2">
                  {selectedProduct.sizes && selectedProduct.sizes.map((sizeObj) => (
                    <button
                      key={sizeObj.size}
                      onClick={() => sizeObj.stock > 0 && setSelectedSize(sizeObj.size)}
                      disabled={sizeObj.stock === 0}
                      className={`py-3 rounded-lg font-semibold transition-all ${
                        sizeObj.stock === 0 
                          ? 'bg-gray-100 text-gray-400 cursor-not-allowed line-through' 
                          : selectedSize === sizeObj.size 
                            ? 'bg-black text-white ring-2 ring-red-600' 
                            : 'bg-white border-2 border-gray-200 hover:border-black'
                      }`}
                    >
                      {sizeObj.size}
                    </button>
                  ))}
                </div>
                {selectedSize && (
                  <div className="mt-3 text-sm text-green-600 font-medium flex items-center space-x-1">
                    <Check size={16} />
                    <span>
                      {selectedProduct.sizes.find(s => s.size === selectedSize)?.stock} pairs available
                    </span>
                  </div>
                )}
              </div>

              <button
                onClick={() => {
                  if (selectedSize) {
                    addToCart(selectedProduct, selectedSize, 1);
                    alert('Added to cart! 🎉');
                  } else {
                    alert('Please select a size');
                  }
                }}
                disabled={!selectedSize}
                className="w-full bg-black hover:bg-red-600 disabled:bg-gray-300 text-white py-4 rounded-lg font-bold text-lg transition-all"
              >
                {selectedSize ? 'ADD TO CART' : 'SELECT SIZE FIRST'}
              </button>

              <div className="bg-gray-50 p-6 rounded-xl border border-gray-200">
                <div className="font-semibold mb-3 flex items-center space-x-2">
                  <MapPin size={18} className="text-red-600" />
                  <span>Visit Our Physical Store</span>
                </div>
                <div className="text-sm text-gray-700 space-y-1 ml-6">
                  <p className="font-medium">Dynamic Mall, Shop ML55, 1st Floor</p>
                  <p>Tom Mboya Street, Nairobi CBD</p>
                  <p className="text-red-600 font-semibold flex items-center space-x-1 mt-2">
                    <Phone size={14} />
                    <span>{settings?.phone || '+254 748 921 804'}</span>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'blog' && (
        <div className="container mx-auto px-4 py-12">
          <button
            onClick={() => {
              setView('store');
              setSelectedBlog(null);
              setTimeout(() => {
                const blogSection = document.getElementById('blog-section');
                if (blogSection) blogSection.scrollIntoView({ behavior: 'smooth' });
              }, 100);
            }}
            className="mb-8 text-gray-600 hover:text-black transition flex items-center space-x-2"
          >
            <span>←</span>
            <span>Back to Blog</span>
          </button>

          {selectedBlogLoading ? (
            <div className="text-gray-600">Loading article...</div>
          ) : selectedBlog ? (
            <div className="max-w-4xl mx-auto">
              <div className="aspect-[16/9] bg-gray-100 rounded-2xl overflow-hidden mb-6">
                {selectedBlog.image_url ? (
                  <img
                    src={`${API_BASE_URL}${selectedBlog.image_url}`}
                    alt={selectedBlog.title}
                    className="w-full h-full object-cover"
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-500 text-sm">
                    Image placeholder
                  </div>
                )}
              </div>
              <div className="text-sm text-gray-500 mb-2">{selectedBlog.created_at}</div>
              <h1 className="text-3xl sm:text-4xl font-bold mb-4">{selectedBlog.title}</h1>
              <div
                className="prose max-w-none text-gray-700"
                dangerouslySetInnerHTML={{ __html: renderBlogContent(selectedBlog.content || selectedBlog.excerpt || '') }}
              />
            </div>
          ) : (
            <div className="text-gray-600">Article not found.</div>
          )}
        </div>
      )}

      {view === 'cart' && (
        <div className="container mx-auto px-4 py-12">
          <h1 className="text-3xl sm:text-4xl font-bold mb-8">Shopping Cart</h1>
          
          {cart.length === 0 ? (
            <div className="text-center py-16">
              <div className="bg-gray-100 rounded-full w-32 h-32 flex items-center justify-center mx-auto mb-6">
                <ShoppingCart size={64} className="text-gray-300" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Your cart is empty</h2>
              <p className="text-gray-600 mb-8">Add some amazing shoes to get started!</p>
              <button 
                onClick={() => setView('store')}
                className="bg-black text-white px-8 py-3 rounded-lg hover:bg-red-600 transition font-semibold"
              >
                Continue Shopping
              </button>
            </div>
          ) : (
            <div className="grid lg:grid-cols-3 gap-8">
              <div className="lg:col-span-2 space-y-4">
                {cart.map(item => (
                  <div key={item.id} className="bg-white rounded-xl p-4 sm:p-6 shadow-md flex items-center space-x-4 sm:space-x-6">
                      <img 
                        src={`${API_BASE_URL}${item.product.image_url}`}
                        alt={getPublicTitle(item.product)}
                        className="w-20 h-20 sm:w-24 sm:h-24 object-cover rounded-lg"
                      />
                      <div className="flex-1">
                        <h3 className="font-bold text-base sm:text-lg">{getPublicTitle(item.product)}</h3>
                        <div className="text-sm text-gray-600">{item.product.color} • Size {item.size}</div>
                        <div className="text-red-600 font-semibold mt-1">KES {item.price.toLocaleString()}</div>
                      </div>
                    <div className="flex items-center space-x-2 sm:space-x-3">
                      <button 
                        onClick={() => updateCartQuantity(item.id, item.quantity - 1)}
                        className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg border-2 border-gray-300 hover:border-black transition flex items-center justify-center font-bold"
                      >
                      </button>
                      <span className="w-6 sm:w-8 text-center font-semibold">{item.quantity}</span>
                      <button 
                        onClick={() => updateCartQuantity(item.id, item.quantity + 1)}
                        className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg border-2 border-gray-300 hover:border-black transition flex items-center justify-center font-bold"
                      >
                      </button>
                    </div>
                    <button 
                      onClick={() => removeFromCart(item.id)}
                      className="text-red-600 hover:text-red-700 transition p-2"
                    >
                      <X size={20} />
                    </button>
                  </div>
                ))}
              </div>

              <div className="lg:col-span-1">
                <div className="bg-white rounded-xl p-6 shadow-md sticky top-24">
                  <h2 className="text-xl font-bold mb-6">Order Summary</h2>
                  
                  <div className="space-y-3 mb-6">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Subtotal</span>
                      <span className="font-semibold">KES {getCartTotal().toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Delivery</span>
                      <span className="font-semibold text-sm">Calculated at checkout</span>
                    </div>
                  </div>
                  
                  <div className="border-t pt-4 mb-6">
                    <div className="flex justify-between text-lg">
                      <span className="font-bold">Total</span>
                      <span className="font-bold text-red-600">KES {getCartTotal().toLocaleString()}</span>
                    </div>
                  </div>

                  <button 
                    onClick={() => {
                      if (!authUser) {
                        setAuthOpen(true);
                        setAuthMode('login');
                        setPostAuthView('checkout');
                        return;
                      }
                      setView('checkout');
                    }}
                    className="w-full bg-black hover:bg-red-600 text-white py-4 rounded-lg font-bold transition-all transform hover:scale-105"
                  >
                    Proceed to Checkout
                  </button>

                  <button 
                    onClick={() => setView('store')}
                    className="w-full mt-3 border-2 border-gray-200 hover:border-black py-3 rounded-lg font-semibold transition"
                  >
                    Continue Shopping
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {view === 'checkout' && (
        authUser ? (
          <CheckoutView 
            cart={cart} 
            deliveryZones={deliveryZones}
            settings={settings}
            onSubmit={handleCheckout}
            onBack={() => setView('cart')}
          />
        ) : (
          <div className="container mx-auto px-4 py-12">
            <div className="max-w-lg mx-auto bg-white rounded-xl p-6 shadow-md text-center">
              <h2 className="text-2xl font-bold mb-2">Sign in to continue</h2>
              <p className="text-gray-600 mb-6">Please sign in or create an account to checkout.</p>
              <button
                onClick={() => { setAuthOpen(true); setAuthMode('login'); setPostAuthView('checkout'); }}
                className="bg-black hover:bg-red-600 text-white px-6 py-3 rounded-lg font-semibold transition"
              >
                Sign In
              </button>
            </div>
          </div>
        )
      )}

      {view === 'wishlist' && (
        <div className="container mx-auto px-4 py-12">
          <h1 className="text-3xl sm:text-4xl font-bold mb-8">My Wishlist</h1>
          {wishlist.length === 0 ? (
            <div className="text-center py-16">
              <Heart size={64} className="mx-auto text-gray-300 mb-4" />
              <h2 className="text-2xl font-bold mb-2">Your wishlist is empty</h2>
              <button 
                onClick={() => setView('store')}
                className="bg-black text-white px-8 py-3 rounded-lg hover:bg-red-600 transition mt-4"
              >
                Start Shopping
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
              {products.filter(p => wishlist.includes(p.id)).map(product => renderProductCard(product))}
            </div>
          )}
        </div>
      )}

      {view === 'about' && (
        <div className="container mx-auto px-4 py-12">
          <div className="max-w-4xl mx-auto space-y-6">
            <h1 className="text-3xl sm:text-4xl font-bold">About Us</h1>
            <p className="text-gray-700">
              Shoes Nexus Kenya is a Nairobi-based footwear retailer offering a wide range of sandals, shoes, heels, and more footwear and accessories for everyday and special occasions — including sandals, sneakers, heels, official shoes, and more.
            </p>
            <p className="text-gray-700">
              We serve customers through our physical store Dynamic Mall Shop ML55, 1st Floor in Nairobi CBD and multiple online channels. Whether you prefer to shop in person or order online, we aim to make it easy to find the right style and size, with dependable customer support and convenient delivery options.
            </p>
            <div>
              <h2 className="text-xl font-bold mb-2">How We Sell</h2>
              <p className="text-gray-700">In-store shopping at our Nairobi CBD Dynamic Mall Shop ML55, 1st Floor outlet</p>
              <p className="text-gray-700">Online orders via our website (shoesnexus.com)</p>
              <p className="text-gray-700">Orders via Instagram DMs and WhatsApp</p>
              <p className="text-gray-700">Walk-in purchases and store pick-ups</p>
            </div>
            <p className="text-gray-800 font-semibold">
              Our goal is simple: great shoes, fair pricing, and a smooth buying experience — online and offline.
            </p>
          </div>
        </div>
      )}

      {view === 'locations' && (
        <div className="container mx-auto px-4 py-12">
          <div className="max-w-4xl mx-auto space-y-6">
            <h1 className="text-3xl sm:text-4xl font-bold">Locations</h1>
            <div>
              <h2 className="text-xl font-bold mb-2">Physical Store</h2>
              <p className="text-gray-700">
                Dynamic Mall, Shop ML55, 1st Floor
                <br />
                Tom Mboya Street, Nairobi CBD, Kenya
              </p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Online Store & Social Media</h2>
              <p className="text-gray-700 mb-2">
                We serve customers across Kenya and beyond through our online channels:
              </p>
              <p className="text-gray-700">Website: shoesnexus.com</p>
              <p className="text-gray-700">Instagram: @shoesnexuskenya</p>
              <p className="text-gray-700">Facebook: Shoes Nexus Kenya</p>
              <p className="text-gray-700">X (Twitter): @ShoeNexus</p>
              <p className="text-gray-700">TikTok: @shoesnexus</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Sales Channels</h2>
              <p className="text-gray-700">Website</p>
              <p className="text-gray-700">Instagram DMs</p>
              <p className="text-gray-700">WhatsApp</p>
              <p className="text-gray-700">Physical store (Nairobi CBD)</p>
            </div>
          </div>
        </div>
      )}

      {view === 'career' && (
        <div className="container mx-auto px-4 py-12">
          <div className="max-w-4xl mx-auto space-y-6">
            <h1 className="text-3xl sm:text-4xl font-bold">Career</h1>
            <p className="text-gray-700">
              Shoes Nexus Kenya is a growing mom-and-pop retail business built on teamwork and trust.
            </p>
            <div>
              <h2 className="text-xl font-bold mb-2">Our Team</h2>
              <p className="text-gray-700">Cashier / store attendant (in-store operations)</p>
              <p className="text-gray-700">Social media manager (content, customer engagement, order support)</p>
              <p className="text-gray-700">Partner delivery riders and couriers who support fulfillment</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Delivery Partnerships</h2>
              <p className="text-gray-700">Delivery by foot within the CBD (where applicable)</p>
              <p className="text-gray-700">Bodaboda deliveries within Nairobi</p>
              <p className="text-gray-700">Courier services for deliveries outside Nairobi and nationwide</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Open Roles</h2>
              <p className="text-gray-700">We do not have open vacancies at the moment.</p>
            </div>
            <p className="text-gray-700">
              We will post future opportunities on our official social pages and website contact form when roles open.
            </p>
          </div>
        </div>
      )}

      {view === 'privacy' && (
        <div className="container mx-auto px-4 py-12">
          <div className="max-w-4xl mx-auto space-y-6">
            <h1 className="text-3xl sm:text-4xl font-bold">Privacy Policy</h1>
            <p className="text-gray-700">
              This Privacy Policy describes how shoesnexus.com collects, uses, and discloses your Personal Information when you visit or make a purchase from the Site.
            </p>
            <div>
              <h2 className="text-xl font-bold mb-2">Collecting Personal Information</h2>
              <p className="text-gray-700 mb-2">
                When you visit the Site, we collect certain information about your device, your interaction with the Site, and information necessary to process your purchases. We may also collect additional information if you contact us for customer support.
              </p>
              <h3 className="text-lg font-semibold mb-1">Device information</h3>
              <p className="text-gray-700">
                Examples: browser version, IP address, time zone, cookie information, what sites or products you view, search terms, and how you interact with the Site.
              </p>
              <p className="text-gray-700">
                Purpose: to load the Site accurately and perform analytics on Site usage to optimize our Site.
              </p>
              <p className="text-gray-700">
                Source: collected automatically using cookies, log files, web beacons, tags, or pixels.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-1">Order information</h3>
              <p className="text-gray-700">
                Examples: name, billing/shipping address, payment information, email address, and phone number.
              </p>
              <p className="text-gray-700">
                Purpose: to fulfill your order, process payment, arrange shipping, provide invoices/order confirmations, communicate with you, screen orders for risk/fraud, and provide marketing where you’ve agreed.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-1">Customer support information</h3>
              <p className="text-gray-700">Purpose: to provide customer support.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Minors</h2>
              <p className="text-gray-700">
                The Site is not intended for individuals under the age of 18. We do not intentionally collect Personal Information from children.
              </p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Sharing Personal Information</h2>
              <p className="text-gray-700">
                We share your Personal Information with service providers to help us provide our services and fulfill contracts with you, and to comply with applicable laws or lawful requests.
              </p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Behavioural Advertising</h2>
              <p className="text-gray-700">
                We may use your information to provide targeted advertisements or marketing communications that may interest you.
              </p>
              <p className="text-gray-700">
                You can opt out of targeted ads via platform ad settings (e.g., Facebook, Google).
              </p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Cookies</h2>
              <p className="text-gray-700">
                We use cookies to power core site functions, remember preferences, and understand site usage. You can manage cookies in your browser settings.
              </p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Do Not Track</h2>
              <p className="text-gray-700">
                We do not alter our data collection practices when we detect a Do Not Track signal because there is no consistent industry standard.
              </p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Changes</h2>
              <p className="text-gray-700">We may update this policy from time to time to reflect operational, legal, or regulatory changes.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Contact</h2>
              <p className="text-gray-700">For questions or complaints, contact us through our website contact form or official social media pages.</p>
            </div>
          </div>
        </div>
      )}

      {view === 'refund' && (
        <div className="container mx-auto px-4 py-12">
          <div className="max-w-4xl mx-auto space-y-6">
            <h1 className="text-3xl sm:text-4xl font-bold">Refund Policy (Exchange & Returns)</h1>
            <div>
              <h2 className="text-xl font-bold mb-2">Exchange Policy (3 Days)</h2>
              <p className="text-gray-700 mb-2">We offer exchanges within 3 days of receiving your item, subject to:</p>
              <p className="text-gray-700">Item must be unused/unworn</p>
              <p className="text-gray-700">Item must be in original condition</p>
              <p className="text-gray-700">Tags must be intact</p>
              <p className="text-gray-700">Proof of purchase is required</p>
              <p className="text-gray-700">Exchange is subject to stock availability (size/style)</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Returns / Refunds (Condition-Based)</h2>
              <p className="text-gray-700 mb-2">Refunds may be considered where there is a reasonable cause, such as:</p>
              <p className="text-gray-700">Wrong item delivered</p>
              <p className="text-gray-700">Verified defect (not caused by wear)</p>
              <p className="text-gray-700">Order fulfillment error</p>
              <p className="text-gray-700 mt-2">
                To qualify: item must be unused/unworn, original tags and packaging intact, and request made within a reasonable timeframe.
              </p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Non-Returnable Items</h2>
              <p className="text-gray-700">Sale/clearance items (unless delivered wrong or defective)</p>
              <p className="text-gray-700">Giveaway items</p>
              <p className="text-gray-700">Gift cards (if applicable)</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Refund Method</h2>
              <p className="text-gray-700">
                Refunds are issued via the original payment method where possible. Cash purchases may be refunded via M-Pesa. Refund amounts cover the value of the item only and may exclude delivery fees or extra courier charges.
              </p>
            </div>
            <p className="text-gray-700 font-semibold">
              Please confirm your order and sizing upon receipt or before leaving the store for in-store purchases.
            </p>
          </div>
        </div>
      )}

      {view === 'terms' && (
        <div className="container mx-auto px-4 py-12">
          <div className="max-w-4xl mx-auto space-y-6">
            <h1 className="text-3xl sm:text-4xl font-bold">Terms of Service</h1>
            <p className="text-gray-700">
              This website is operated by Shoes Nexus Kenya. By visiting our site and/or purchasing from us, you agree to be bound by these Terms of Service.
            </p>
            <div>
              <h2 className="text-xl font-bold mb-2">Online Store Terms</h2>
              <p className="text-gray-700">You agree not to use our products for any illegal or unauthorized purpose, and not to violate any laws in your jurisdiction.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">General Conditions</h2>
              <p className="text-gray-700">We reserve the right to refuse service to anyone at any time. You understand that content may be transferred unencrypted, except payment information which is encrypted during transmission.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Product Information & Availability</h2>
              <p className="text-gray-700">We aim to display products accurately, but colors may vary depending on your screen/device. Product availability may change without notice.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Pricing & Modifications</h2>
              <p className="text-gray-700">Prices may change without notice. We may modify or discontinue the Service at any time.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Accuracy of Billing and Account Information</h2>
              <p className="text-gray-700">You agree to provide current, complete, and accurate purchase information and promptly update your account details.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Third-Party Links</h2>
              <p className="text-gray-700">We are not responsible for third-party websites linked from our site. Use them at your own risk.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Personal Information</h2>
              <p className="text-gray-700">Your submission of personal information is governed by our Privacy Policy.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Prohibited Uses</h2>
              <p className="text-gray-700">You may not use the site for unlawful purposes, to infringe intellectual property, to harass or abuse others, or to upload malicious code.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Limitation of Liability</h2>
              <p className="text-gray-700">To the maximum extent permitted by law, Shoes Nexus Kenya shall not be liable for indirect or consequential damages arising from your use of our Service or products.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Governing Law</h2>
              <p className="text-gray-700">These Terms shall be governed by the laws of Kenya.</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Contact</h2>
              <p className="text-gray-700">For questions about these Terms, contact us via our website contact form or official social media pages.</p>
            </div>
          </div>
        </div>
      )}

      {view === 'shipping' && (
        <div className="container mx-auto px-4 py-12">
          <div className="max-w-4xl mx-auto space-y-6">
            <h1 className="text-3xl sm:text-4xl font-bold">Shipping Policy</h1>
            <p className="text-gray-700">
              We offer delivery within Nairobi and nationwide in Kenya, with additional options for regional and international shipping depending on courier availability.
            </p>
            <div>
              <h2 className="text-xl font-bold mb-2">Delivery Coverage</h2>
              <p className="text-gray-700">Within Nairobi: Same-day delivery where possible</p>
              <p className="text-gray-700">Outside Nairobi (Kenya): Typically 1–2 business days</p>
              <p className="text-gray-700">East Africa: Typically 2–5 business days</p>
              <p className="text-gray-700">International: Typically 10–14 business days</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Delivery Methods</h2>
              <p className="text-gray-700">Delivery by foot (selected areas within Nairobi CBD)</p>
              <p className="text-gray-700">Bodaboda delivery within Nairobi</p>
              <p className="text-gray-700">Courier partners for deliveries outside Nairobi and nationwide</p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Delivery Fees</h2>
              <p className="text-gray-700">
                Nairobi delivery fees vary by location and are communicated at checkout or during order confirmation. Outside Nairobi delivery charges typically range between KES 250–500, depending on destination and courier.
              </p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Payment & Order Processing</h2>
              <p className="text-gray-700">
                Payment methods may include website checkout payments, M-Pesa payments, and store payments for in-store purchases.
              </p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Store Pick-Up</h2>
              <p className="text-gray-700">
                Customers may choose to pick up orders from our store. Pick-up orders should be collected within 7 days of purchase unless otherwise agreed.
              </p>
              <p className="text-gray-700">
                Dynamic Mall, Shop ML55, 1st Floor, Tom Mboya Street, Nairobi CBD.
              </p>
            </div>
            <div>
              <h2 className="text-xl font-bold mb-2">Damages / Wrong Deliveries</h2>
              <p className="text-gray-700">
                If your order arrives damaged or incorrect, contact us immediately so we can resolve it.
              </p>
            </div>
          </div>
        </div>
      )}

      {view === 'account' && (
        <div className="container mx-auto px-4 py-12">
          <div className="max-w-3xl mx-auto">
            <h1 className="text-3xl sm:text-4xl font-bold mb-6">My Account</h1>
            {authUser ? (
              <div className="bg-white rounded-xl p-6 shadow-md mb-8">
                <div className="grid sm:grid-cols-2 gap-6">
                  <div>
                    <div className="text-sm text-gray-500 mb-1">Name</div>
                    <div className="font-semibold">{authUser.name || '—'}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500 mb-1">Email</div>
                    <div className="font-semibold">{authUser.email || '—'}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500 mb-1">Phone</div>
                    <div className="font-semibold">{authUser.phone || '—'}</div>
                  </div>
                  {authUser.isStaff && (
                    <>
                      <div>
                        <div className="text-sm text-gray-500 mb-1">Username</div>
                        <div className="font-semibold">{authUser.username || '—'}</div>
                      </div>
                      <div>
                        <div className="text-sm text-gray-500 mb-1">Role</div>
                        <div className="font-semibold">{authUser.role || '—'}</div>
                      </div>

                      <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                        <h2 className="text-xl font-bold mb-4">Low Stock Alerts</h2>
                        {adminLowStock.length === 0 ? (
                          <p className="text-gray-500">No low stock items.</p>
                        ) : (
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="text-left text-gray-500">
                                  <th className="py-2">Brand</th>
                                  <th className="py-2">Model</th>
                                  <th className="py-2">Color</th>
                                  <th className="py-2">Category</th>
                                  <th className="py-2">Total Stock</th>
                                </tr>
                              </thead>
                              <tbody>
                                {adminLowStock.map(item => (
                                  <tr key={item.id} className="border-t">
                                    <td className="py-2">{item.brand}</td>
                                    <td className="py-2">{item.model}</td>
                                    <td className="py-2">{item.color}</td>
                                    <td className="py-2">{item.category}</td>
                                    <td className="py-2 font-semibold">{item.total_stock}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>

                      <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                        <h2 className="text-xl font-bold mb-4">Source Breakdown (Online Orders)</h2>
                        {adminOrders.length === 0 ? (
                          <p className="text-gray-500">No online orders yet.</p>
                        ) : (
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="text-left text-gray-500">
                                  <th className="py-2">Source</th>
                                  <th className="py-2">Orders</th>
                                  <th className="py-2">Share</th>
                                </tr>
                              </thead>
                              <tbody>
                                {getAdminSourceBreakdown().rows.map(row => (
                                  <tr key={row.source} className="border-t">
                                    <td className="py-2">{row.source}</td>
                                    <td className="py-2">{row.count}</td>
                                    <td className="py-2">{row.percent}%</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>

                      <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                        <h2 className="text-xl font-bold mb-4">Admin Activity Log</h2>
                        {adminAuditLog.length === 0 ? (
                          <p className="text-gray-500">No admin activity yet.</p>
                        ) : (
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="text-left text-gray-500">
                                  <th className="py-2">Time</th>
                                  <th className="py-2">Event</th>
                                  <th className="py-2">Actor</th>
                                  <th className="py-2">Details</th>
                                </tr>
                              </thead>
                              <tbody>
                                {adminAuditLog.map(entry => (
                                  <tr key={entry.id} className="border-t">
                                    <td className="py-2">{entry.created_at}</td>
                                    <td className="py-2">{entry.event_type}</td>
                                    <td className="py-2">{entry.actor || '—'}</td>
                                    <td className="py-2">{entry.details}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
                {authUser.isStaff && authUser.role && authUser.role.toLowerCase() === 'admin' && (
                  <div className="mt-6 flex flex-wrap gap-3">
                    <a
                      href={POS_URL}
                      className="bg-black hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold transition"
                    >
                      Open POS
                    </a>
                    <button
                      onClick={() => { setView('admin'); window.scrollTo(0, 0); }}
                      className="border-2 border-gray-200 hover:border-black px-4 py-2 rounded-lg font-semibold transition"
                    >
                      Website Administration
                    </button>
                  </div>
                )}
                <div className="mt-6 flex flex-wrap gap-3">
                  <button
                    onClick={() => { setAuthOpen(true); setAuthMode('change'); }}
                    className="border-2 border-gray-200 hover:border-black px-4 py-2 rounded-lg font-semibold transition"
                  >
                    Change Password
                  </button>
                  <button
                    onClick={handleLogout}
                    className="bg-black hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold transition"
                  >
                    Sign Out
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl p-6 shadow-md text-center">
                <p className="text-gray-600 mb-4">Please sign in to view your account.</p>
                <button
                  onClick={() => { setAuthOpen(true); setAuthMode('login'); }}
                  className="bg-black hover:bg-red-600 text-white px-6 py-3 rounded-lg font-semibold transition"
                >
                  Sign In
                </button>
              </div>
            )}

            <div className="bg-white rounded-xl p-6 shadow-md">
              <h2 className="text-xl font-bold mb-4">Order History</h2>
              {userOrdersLoading ? (
                <p className="text-gray-500">Loading your orders...</p>
              ) : userOrdersError ? (
                <p className="text-red-600">{userOrdersError}</p>
              ) : userOrders.length === 0 ? (
                <p className="text-gray-500">No orders yet.</p>
              ) : (
                <div className="space-y-4">
                  {userOrders.map(order => (
                    <div key={order.id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="font-semibold">Order #{order.order_number}</div>
                        <div className="text-sm text-gray-500">{order.created_at}</div>
                      </div>
                      <div className="text-sm text-gray-600 mt-1">
                        Status: {order.status || '—'} • Payment: {order.payment_status || '—'}
                      </div>
                      <div className="text-sm text-gray-600">
                        Total: KES {order.total_amount}
                      </div>
                      {order.items && order.items.length > 0 && (
                        <ul className="mt-3 text-sm text-gray-700 space-y-1">
                          {order.items.map((item, idx) => (
                            <li key={idx}>
                              {item.brand} {item.model} ({item.color}) • Size {item.size} • Qty {item.quantity}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {view === 'admin' && (
        <div className="container mx-auto px-4 py-12">
          <div className="max-w-6xl mx-auto">
            <h1 className="text-3xl sm:text-4xl font-bold mb-6">Admin Dashboard</h1>
            {authUser?.isStaff && authUser?.role && authUser.role.toLowerCase() === 'admin' ? (
              <>
                <div className="bg-white rounded-xl p-6 shadow-md mb-8">
                  <p className="text-gray-700 mb-4">
                    Manage products, staff accounts, and sales records. Changes are stored in the shared database.
                  </p>
                    <div className="flex flex-wrap gap-3">
                      <a
                        href={POS_URL}
                        className="bg-black hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold transition"
                      >
                        Open POS
                      </a>
                      <button
                        onClick={() => setAdminRefreshKey(prev => prev + 1)}
                        className="border-2 border-gray-200 hover:border-black px-4 py-2 rounded-lg font-semibold transition"
                      >
                        Refresh Data
                      </button>
                      <button
                        onClick={() => { setView('store'); window.scrollTo(0, 0); }}
                        className="border-2 border-gray-200 hover:border-black px-4 py-2 rounded-lg font-semibold transition"
                      >
                        View Storefront
                    </button>
                  </div>
                </div>

                {adminError && (
                  <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                    {adminError}
                  </div>
                )}

                {adminLoading ? (
                  <div className="text-gray-600">Loading admin data...</div>
                ) : (
                  <>
                    <div className="mb-6">
                      <input
                        className="w-full border-2 border-gray-200 rounded-lg px-3 py-2"
                        placeholder="Search products by brand, model, category, or color"
                        value={adminProductSearch}
                        onChange={(e) => setAdminProductSearch(e.target.value)}
                      />
                    </div>
                    <div className="grid lg:grid-cols-2 gap-6 mb-10">
                      <div className="bg-white rounded-xl p-6 shadow-md">
                        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                          <h2 className="text-xl font-bold">Add Product</h2>
                          <button
                            onClick={handleAdminRegeneratePublic}
                            className="border-2 border-gray-200 hover:border-black px-3 py-2 rounded-lg text-sm font-semibold transition"
                          >
                            Regenerate Public Titles
                          </button>
                        </div>
                        <div className="grid sm:grid-cols-2 gap-4">
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Category (Women/Men/Accessories)"
                            value={adminProductForm.category}
                            onChange={(e) => setAdminProductForm({ ...adminProductForm, category: e.target.value })}
                          />
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Brand"
                            value={adminProductForm.brand}
                            onChange={(e) => setAdminProductForm({ ...adminProductForm, brand: e.target.value })}
                          />
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Model"
                            value={adminProductForm.model}
                            onChange={(e) => setAdminProductForm({ ...adminProductForm, model: e.target.value })}
                          />
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Color"
                            value={adminProductForm.color}
                            onChange={(e) => setAdminProductForm({ ...adminProductForm, color: e.target.value })}
                          />
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Image URL (e.g. /images/women-sandals/...)"
                            value={adminProductForm.image_url}
                            onChange={(e) => setAdminProductForm({ ...adminProductForm, image_url: e.target.value })}
                          />
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Public Brand (website label)"
                            value={adminProductForm.public_brand}
                            onChange={(e) => setAdminProductForm({ ...adminProductForm, public_brand: e.target.value })}
                          />
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Public Title (SEO name)"
                            value={adminProductForm.public_title}
                            onChange={(e) => setAdminProductForm({ ...adminProductForm, public_title: e.target.value })}
                          />
                          <input
                            type="file"
                            accept="image/*"
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            onChange={(e) => handleAdminImageUpload(e.target.files?.[0], 'create')}
                          />
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Buying Price"
                            value={adminProductForm.buying_price}
                            onChange={(e) => setAdminProductForm({ ...adminProductForm, buying_price: e.target.value })}
                            />
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Selling Price"
                            value={adminProductForm.selling_price}
                            onChange={(e) => setAdminProductForm({ ...adminProductForm, selling_price: e.target.value })}
                          />
                        </div>
                        <textarea
                          className="w-full mt-4 border-2 border-gray-200 rounded-lg px-3 py-2"
                          rows={3}
                          placeholder="Sizes as size:stock (e.g. 37:5, 38:3). Leave empty for accessories."
                          value={adminProductForm.sizes}
                          onChange={(e) => setAdminProductForm({ ...adminProductForm, sizes: e.target.value })}
                        />
                        <textarea
                          className="w-full mt-3 border-2 border-gray-200 rounded-lg px-3 py-2"
                          rows={3}
                          placeholder="Public Description (SEO copy)"
                          value={adminProductForm.public_description}
                          onChange={(e) => setAdminProductForm({ ...adminProductForm, public_description: e.target.value })}
                        />
                        <button
                          onClick={handleAdminCreateProduct}
                          className="mt-4 bg-black hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold transition"
                          disabled={adminUploadLoading}
                        >
                          {adminUploadLoading ? 'Uploading Image...' : 'Create Product'}
                        </button>
                      </div>

                      <div className="bg-white rounded-xl p-6 shadow-md">
                        <h2 className="text-xl font-bold mb-4">
                          {adminEditingStaff ? `Edit Staff User #${adminEditingStaff.id}` : 'Create Staff User'}
                        </h2>
                        <div className="space-y-3">
                          <input
                            className="w-full border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Username"
                            value={adminStaffForm.username}
                            onChange={(e) => setAdminStaffForm({ ...adminStaffForm, username: e.target.value })}
                          />
                          <input
                            type="password"
                            className="w-full border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder={adminEditingStaff ? 'New Password (required for update)' : 'Password'}
                            value={adminStaffForm.password}
                            onChange={(e) => setAdminStaffForm({ ...adminStaffForm, password: e.target.value })}
                          />
                          <select
                            className="w-full border-2 border-gray-200 rounded-lg px-3 py-2"
                            value={adminStaffForm.role}
                            onChange={(e) => setAdminStaffForm({ ...adminStaffForm, role: e.target.value })}
                          >
                            <option>Cashier</option>
                            <option>Manager</option>
                            <option>Admin</option>
                          </select>
                        </div>
                        <div className="mt-4 flex flex-wrap gap-3">
                          <button
                            onClick={() => {
                              if (adminEditingStaff) {
                                handleAdminUpdateStaff(adminEditingStaff.id);
                              } else {
                                handleAdminCreateStaff();
                              }
                            }}
                            className="bg-black hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold transition"
                          >
                            {adminEditingStaff ? 'Update Staff' : 'Create Staff'}
                          </button>
                          {adminEditingStaff && (
                            <button
                              onClick={cancelEditStaff}
                              className="border-2 border-gray-200 hover:border-black px-4 py-2 rounded-lg font-semibold transition"
                            >
                              Cancel Edit
                            </button>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                      <h2 className="text-xl font-bold mb-4">
                        {adminEditBlog ? `Edit Blog Post #${adminEditBlog.id}` : 'Create Blog Post'}
                      </h2>
                      <div className="grid sm:grid-cols-2 gap-4">
                        <input
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Title"
                          value={adminBlogForm.title}
                          onChange={(e) => setAdminBlogForm({ ...adminBlogForm, title: e.target.value })}
                        />
                        <input
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Category (e.g. Trends, Style Tips)"
                          value={adminBlogForm.category}
                          onChange={(e) => setAdminBlogForm({ ...adminBlogForm, category: e.target.value })}
                        />
                        <input
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Image URL (e.g. /images/admin-uploads/...)"
                          value={adminBlogForm.image_url}
                          onChange={(e) => setAdminBlogForm({ ...adminBlogForm, image_url: e.target.value })}
                        />
                        <input
                          type="file"
                          accept="image/*"
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          onChange={(e) => handleAdminImageUpload(e.target.files?.[0], 'blog')}
                        />
                        <label className="flex items-center gap-2 text-sm text-gray-700">
                          <input
                            type="checkbox"
                            checked={adminBlogForm.is_published}
                            onChange={(e) => setAdminBlogForm({ ...adminBlogForm, is_published: e.target.checked })}
                          />
                          Published
                        </label>
                      </div>
                      <textarea
                        className="w-full mt-4 border-2 border-gray-200 rounded-lg px-3 py-2"
                        rows={2}
                        placeholder="Short excerpt"
                        value={adminBlogForm.excerpt}
                        onChange={(e) => setAdminBlogForm({ ...adminBlogForm, excerpt: e.target.value })}
                      />
                      <textarea
                        className="w-full mt-3 border-2 border-gray-200 rounded-lg px-3 py-2"
                        rows={4}
                        placeholder="Blog content"
                        value={adminBlogForm.content}
                        onChange={(e) => setAdminBlogForm({ ...adminBlogForm, content: e.target.value })}
                      />
                      <div className="mt-4 flex flex-wrap gap-3">
                        <button
                          onClick={adminEditBlog ? handleAdminUpdateBlog : handleAdminCreateBlog}
                          className="bg-black hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold transition"
                          disabled={adminUploadLoading}
                        >
                          {adminUploadLoading ? 'Uploading Image...' : (adminEditBlog ? 'Update Post' : 'Create Post')}
                        </button>
                        {adminEditBlog && (
                          <button
                            onClick={() => { setAdminEditBlog(null); setAdminBlogForm({ title: '', category: '', excerpt: '', content: '', image_url: '', is_published: true }); }}
                            className="border-2 border-gray-200 hover:border-black px-4 py-2 rounded-lg font-semibold transition"
                          >
                            Cancel Edit
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                      <h2 className="text-xl font-bold mb-4">Blog Posts</h2>
                      {adminBlogPosts.length === 0 ? (
                        <p className="text-gray-500">No blog posts yet.</p>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-left text-gray-500">
                                <th className="py-2">ID</th>
                                <th className="py-2">Title</th>
                                <th className="py-2">Category</th>
                                <th className="py-2">Status</th>
                                <th className="py-2">Action</th>
                              </tr>
                            </thead>
                            <tbody>
                              {adminBlogPosts.map(post => (
                                <tr key={post.id} className="border-t">
                                  <td className="py-2">{post.id}</td>
                                  <td className="py-2">{post.title}</td>
                                  <td className="py-2">{post.category || '-'}</td>
                                  <td className="py-2">{post.is_published ? 'Published' : 'Draft'}</td>
                                  <td className="py-2">
                                    <div className="flex flex-wrap gap-2">
                                      <button
                                        onClick={() => startEditBlog(post)}
                                        className="text-blue-600 hover:underline"
                                      >
                                        Edit
                                      </button>
                                      <button
                                        onClick={() => handleAdminToggleBlog(post.id)}
                                        className="text-red-600 hover:underline"
                                      >
                                        {post.is_published ? 'Unpublish' : 'Publish'}
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>

                    <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                      <h2 className="text-xl font-bold mb-4">
                        {adminEditSection ? `Edit Section #${adminEditSection.id}` : 'Create Home Section'}
                      </h2>
                      <div className="grid sm:grid-cols-2 gap-4">
                        <input
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Section Title"
                          value={adminSectionForm.title}
                          onChange={(e) => setAdminSectionForm({ ...adminSectionForm, title: e.target.value })}
                        />
                        <input
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Category Label Match (e.g. women, men)"
                          value={adminSectionForm.category_label}
                          onChange={(e) => setAdminSectionForm({ ...adminSectionForm, category_label: e.target.value })}
                        />
                        <input
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Category Match (optional)"
                          value={adminSectionForm.category_match}
                          onChange={(e) => setAdminSectionForm({ ...adminSectionForm, category_match: e.target.value })}
                        />
                        <input
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Model keywords (comma-separated)"
                          value={adminSectionForm.model_keywords}
                          onChange={(e) => setAdminSectionForm({ ...adminSectionForm, model_keywords: e.target.value })}
                        />
                        <select
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          value={adminSectionForm.filter_category}
                          onChange={(e) => setAdminSectionForm({ ...adminSectionForm, filter_category: e.target.value })}
                        >
                          <option>All</option>
                          <option>Women</option>
                          <option>Men</option>
                        </select>
                        <select
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          value={adminSectionForm.filter_type}
                          onChange={(e) => setAdminSectionForm({ ...adminSectionForm, filter_type: e.target.value })}
                        >
                          <option>All</option>
                          <option>Sandals</option>
                          <option>Slides</option>
                          <option>Sneakers</option>
                          <option>Heels</option>
                          <option>Accessories</option>
                        </select>
                        <input
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Limit (leave empty for all)"
                          value={adminSectionForm.limit_count}
                          onChange={(e) => setAdminSectionForm({ ...adminSectionForm, limit_count: e.target.value })}
                        />
                        <input
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Sort order (0 = first)"
                          value={adminSectionForm.sort_order}
                          onChange={(e) => setAdminSectionForm({ ...adminSectionForm, sort_order: e.target.value })}
                        />
                        <label className="flex items-center gap-2 text-sm text-gray-700">
                          <input
                            type="checkbox"
                            checked={adminSectionForm.alternate_brands}
                            onChange={(e) => setAdminSectionForm({ ...adminSectionForm, alternate_brands: e.target.checked })}
                          />
                          Alternate brands
                        </label>
                        <label className="flex items-center gap-2 text-sm text-gray-700">
                          <input
                            type="checkbox"
                            checked={adminSectionForm.allow_out_of_stock}
                            onChange={(e) => setAdminSectionForm({ ...adminSectionForm, allow_out_of_stock: e.target.checked })}
                          />
                          Allow out of stock
                        </label>
                        <label className="flex items-center gap-2 text-sm text-gray-700">
                          <input
                            type="checkbox"
                            checked={adminSectionForm.is_active}
                            onChange={(e) => setAdminSectionForm({ ...adminSectionForm, is_active: e.target.checked })}
                          />
                          Active
                        </label>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-3">
                        <button
                          onClick={adminEditSection ? handleAdminUpdateSection : handleAdminCreateSection}
                          className="bg-black hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold transition"
                        >
                          {adminEditSection ? 'Update Section' : 'Create Section'}
                        </button>
                        {adminEditSection && (
                          <button
                            onClick={() => {
                              setAdminEditSection(null);
                              setAdminSectionForm({
                                title: '',
                                category_label: '',
                                category_match: '',
                                model_keywords: '',
                                filter_category: 'All',
                                filter_type: 'All',
                                limit_count: '',
                                alternate_brands: false,
                                allow_out_of_stock: false,
                                sort_order: 0,
                                is_active: true
                              });
                            }}
                            className="border-2 border-gray-200 hover:border-black px-4 py-2 rounded-lg font-semibold transition"
                          >
                            Cancel Edit
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                      <h2 className="text-xl font-bold mb-4">Homepage Sections</h2>
                      {adminSections.length === 0 ? (
                        <p className="text-gray-500">No sections yet.</p>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-left text-gray-500">
                                <th className="py-2">ID</th>
                                <th className="py-2">Title</th>
                                <th className="py-2">Category</th>
                                <th className="py-2">Type</th>
                                <th className="py-2">Status</th>
                                <th className="py-2">Action</th>
                              </tr>
                            </thead>
                            <tbody>
                              {adminSections.map(section => (
                                <tr key={section.id} className="border-t">
                                  <td className="py-2">{section.id}</td>
                                  <td className="py-2">{section.title}</td>
                                  <td className="py-2">{section.filter_category || 'All'}</td>
                                  <td className="py-2">{section.filter_type || 'All'}</td>
                                  <td className="py-2">{section.is_active ? 'Active' : 'Inactive'}</td>
                                  <td className="py-2">
                                    <div className="flex flex-wrap gap-2">
                                      <button
                                        onClick={() => startEditSection(section)}
                                        className="text-blue-600 hover:underline"
                                      >
                                        Edit
                                      </button>
                                      <button
                                        onClick={() => handleAdminToggleSection(section.id)}
                                        className="text-red-600 hover:underline"
                                      >
                                        {section.is_active ? 'Disable' : 'Enable'}
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>

                    <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                      <h2 className="text-xl font-bold mb-4">Reset Customer Password</h2>
                      <div className="grid sm:grid-cols-2 gap-4">
                        <input
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Email or Phone"
                          value={adminUserResetForm.identifier}
                          onChange={(e) => setAdminUserResetForm({ ...adminUserResetForm, identifier: e.target.value })}
                        />
                        <input
                          type="password"
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="New Password"
                          value={adminUserResetForm.new_password}
                          onChange={(e) => setAdminUserResetForm({ ...adminUserResetForm, new_password: e.target.value })}
                        />
                      </div>
                      <button
                        onClick={handleAdminResetUserPassword}
                        className="mt-4 bg-black hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold transition"
                      >
                        Reset Password
                      </button>
                    </div>

                    <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                      <h2 className="text-xl font-bold mb-4">Customer Accounts</h2>
                      <div className="flex flex-wrap gap-3 mb-4">
                        <input
                          className="flex-1 min-w-[220px] border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Search by name, email, or phone"
                          value={adminUserSearch}
                          onChange={(e) => setAdminUserSearch(e.target.value)}
                        />
                        <button
                          onClick={handleAdminSearchUsers}
                          className="bg-black hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold transition"
                        >
                          Search
                        </button>
                      </div>
                      {adminUsers.length === 0 ? (
                        <p className="text-gray-500">No users found.</p>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-left text-gray-500">
                                <th className="py-2">ID</th>
                                <th className="py-2">Name</th>
                                <th className="py-2">Email</th>
                                <th className="py-2">Phone</th>
                                <th className="py-2">Action</th>
                              </tr>
                            </thead>
                            <tbody>
                              {adminUsers.map(user => (
                                <tr key={user.id} className="border-t">
                                  <td className="py-2">{user.id}</td>
                                  <td className="py-2">{user.name}</td>
                                  <td className="py-2">{user.email}</td>
                                  <td className="py-2">{user.phone}</td>
                                  <td className="py-2">
                                    <button
                                      onClick={() => setAdminUserResetForm({ ...adminUserResetForm, identifier: user.email || user.phone })}
                                      className="text-blue-600 hover:underline"
                                    >
                                      Use
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>

                    <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                      <h2 className="text-xl font-bold mb-4">Reset Staff Password</h2>
                      <div className="grid sm:grid-cols-2 gap-4">
                        <input
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="Staff Username"
                          value={adminStaffResetForm.username}
                          onChange={(e) => setAdminStaffResetForm({ ...adminStaffResetForm, username: e.target.value })}
                        />
                        <input
                          type="password"
                          className="border-2 border-gray-200 rounded-lg px-3 py-2"
                          placeholder="New Password"
                          value={adminStaffResetForm.new_password}
                          onChange={(e) => setAdminStaffResetForm({ ...adminStaffResetForm, new_password: e.target.value })}
                        />
                      </div>
                      <button
                        onClick={handleAdminResetStaffPassword}
                        className="mt-4 bg-black hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold transition"
                      >
                        Reset Staff Password
                      </button>
                    </div>

                    <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                      <h2 className="text-xl font-bold mb-4">Products</h2>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-gray-500">
                              <th className="py-2">ID</th>
                              <th className="py-2">Brand</th>
                              <th className="py-2">Model</th>
                              <th className="py-2">Category</th>
                              <th className="py-2">Price</th>
                              <th className="py-2">Status</th>
                              <th className="py-2">Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {adminProducts.filter(product => {
                              if (!adminProductSearch.trim()) return true;
                              const term = adminProductSearch.toLowerCase();
                              return [
                                product.brand,
                                product.model,
                                product.category,
                                product.color
                              ].some(value => (value || '').toLowerCase().includes(term));
                            }).map(product => (
                              <tr key={product.id} className="border-t">
                                <td className="py-2">{product.id}</td>
                                <td className="py-2">{product.brand}</td>
                                <td className="py-2">{product.model}</td>
                                <td className="py-2">{product.category}</td>
                                <td className="py-2">KES {product.selling_price}</td>
                                <td className="py-2">{product.is_active ? 'Active' : 'Inactive'}</td>
                                <td className="py-2">
                                  <div className="flex flex-wrap gap-2">
                                    <button
                                      onClick={() => openEditProduct(product)}
                                      className="text-blue-600 hover:underline"
                                    >
                                      Edit
                                    </button>
                                    {product.is_active ? (
                                      <button
                                        onClick={() => handleAdminDeactivateProduct(product.id)}
                                        className="text-red-600 hover:underline"
                                      >
                                        Deactivate
                                      </button>
                                    ) : (
                                      <button
                                        onClick={() => handleAdminActivateProduct(product.id)}
                                        className="text-green-600 hover:underline"
                                      >
                                        Activate
                                      </button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {adminEditProduct && (
                      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
                        <div className="w-full max-w-lg bg-white rounded-xl p-6 shadow-2xl">
                          <div className="flex items-center justify-between mb-4">
                            <h3 className="text-xl font-bold">Edit Product #{adminEditProduct.id}</h3>
                            <button
                              onClick={() => setAdminEditProduct(null)}
                              className="text-gray-500 hover:text-black"
                            >
                              X
                            </button>
                          </div>
                          <div className="grid sm:grid-cols-2 gap-4">
                            <input
                              className="border-2 border-gray-200 rounded-lg px-3 py-2"
                              placeholder="Category"
                              value={adminEditForm.category}
                              onChange={(e) => setAdminEditForm({ ...adminEditForm, category: e.target.value })}
                            />
                            <input
                              className="border-2 border-gray-200 rounded-lg px-3 py-2"
                              placeholder="Brand"
                              value={adminEditForm.brand}
                              onChange={(e) => setAdminEditForm({ ...adminEditForm, brand: e.target.value })}
                            />
                            <input
                              className="border-2 border-gray-200 rounded-lg px-3 py-2"
                              placeholder="Model"
                              value={adminEditForm.model}
                              onChange={(e) => setAdminEditForm({ ...adminEditForm, model: e.target.value })}
                            />
                            <input
                              className="border-2 border-gray-200 rounded-lg px-3 py-2"
                              placeholder="Color"
                              value={adminEditForm.color}
                              onChange={(e) => setAdminEditForm({ ...adminEditForm, color: e.target.value })}
                            />
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Image URL (e.g. /images/women-sandals/...)"
                            value={adminEditForm.image_url}
                            onChange={(e) => setAdminEditForm({ ...adminEditForm, image_url: e.target.value })}
                          />
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Public Brand (website label)"
                            value={adminEditForm.public_brand}
                            onChange={(e) => setAdminEditForm({ ...adminEditForm, public_brand: e.target.value })}
                          />
                          <input
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            placeholder="Public Title (SEO name)"
                            value={adminEditForm.public_title}
                            onChange={(e) => setAdminEditForm({ ...adminEditForm, public_title: e.target.value })}
                          />
                          <input
                            type="file"
                            accept="image/*"
                            className="border-2 border-gray-200 rounded-lg px-3 py-2"
                            onChange={(e) => handleAdminImageUpload(e.target.files?.[0], 'edit')}
                          />
                            <input
                              className="border-2 border-gray-200 rounded-lg px-3 py-2"
                              placeholder="Buying Price"
                              value={adminEditForm.buying_price}
                              onChange={(e) => setAdminEditForm({ ...adminEditForm, buying_price: e.target.value })}
                            />
                            <input
                              className="border-2 border-gray-200 rounded-lg px-3 py-2"
                              placeholder="Selling Price"
                              value={adminEditForm.selling_price}
                              onChange={(e) => setAdminEditForm({ ...adminEditForm, selling_price: e.target.value })}
                            />
                          </div>
                          <textarea
                            className="w-full mt-4 border-2 border-gray-200 rounded-lg px-3 py-2"
                            rows={3}
                            placeholder="Sizes as size:stock (e.g. 37:5, 38:3)"
                            value={adminEditForm.sizes}
                            onChange={(e) => setAdminEditForm({ ...adminEditForm, sizes: e.target.value })}
                          />
                          <textarea
                            className="w-full mt-3 border-2 border-gray-200 rounded-lg px-3 py-2"
                            rows={3}
                            placeholder="Public Description (SEO copy)"
                            value={adminEditForm.public_description}
                            onChange={(e) => setAdminEditForm({ ...adminEditForm, public_description: e.target.value })}
                          />
                          <div className="mt-4 flex gap-3">
                            <button
                              onClick={handleAdminUpdateProduct}
                              className="bg-black hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold transition"
                              disabled={adminUploadLoading}
                            >
                              {adminUploadLoading ? 'Uploading Image...' : 'Save Changes'}
                            </button>
                            <button
                              onClick={() => setAdminEditProduct(null)}
                              className="border-2 border-gray-200 hover:border-black px-4 py-2 rounded-lg font-semibold transition"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="bg-white rounded-xl p-6 shadow-md mb-10">
                      <h2 className="text-xl font-bold mb-4">Staff</h2>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-gray-500">
                              <th className="py-2">ID</th>
                              <th className="py-2">Username</th>
                              <th className="py-2">Role</th>
                              <th className="py-2">Status</th>
                              <th className="py-2">Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {adminStaff.map(staff => (
                              <tr key={staff.id} className="border-t">
                                <td className="py-2">{staff.id}</td>
                                <td className="py-2">{staff.username}</td>
                                <td className="py-2">{staff.role}</td>
                                <td className="py-2">{staff.is_active ? 'Active' : 'Inactive'}</td>
                                <td className="py-2">
                                  <div className="flex flex-wrap gap-2">
                                    <button
                                      onClick={() => startEditStaff(staff)}
                                      className="text-blue-600 hover:underline"
                                    >
                                      Edit
                                    </button>
                                    {staff.is_active ? (
                                      <button
                                        onClick={() => handleAdminDeactivateStaff(staff.id)}
                                        className="text-red-600 hover:underline"
                                      >
                                        Deactivate
                                      </button>
                                    ) : (
                                      <button
                                        onClick={() => handleAdminActivateStaff(staff.id)}
                                        className="text-green-600 hover:underline"
                                      >
                                        Activate
                                      </button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div className="bg-white rounded-xl p-6 shadow-md">
                      <h2 className="text-xl font-bold mb-4">Sales (POS)</h2>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-gray-500">
                              <th className="py-2">ID</th>
                              <th className="py-2">Product</th>
                              <th className="py-2">Qty</th>
                              <th className="py-2">Revenue</th>
                              <th className="py-2">Date</th>
                            </tr>
                          </thead>
                          <tbody>
                            {adminSales.map(sale => (
                              <tr key={sale.id} className="border-t">
                                <td className="py-2">{sale.id}</td>
                                <td className="py-2">{sale.brand} {sale.model}</td>
                                <td className="py-2">{sale.quantity}</td>
                                <td className="py-2">KES {sale.revenue}</td>
                                <td className="py-2">{sale.sale_date || '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div className="bg-white rounded-xl p-6 shadow-md mt-10">
                      <h2 className="text-xl font-bold mb-4">Online Orders</h2>
                      {adminOrders.length === 0 ? (
                        <p className="text-gray-500">No online orders yet.</p>
                      ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="text-left text-gray-500">
                                  <th className="py-2">Order #</th>
                                  <th className="py-2">Customer</th>
                                  <th className="py-2">Phone</th>
                                  <th className="py-2">Total</th>
                                  <th className="py-2">Delivery</th>
                                  <th className="py-2">Source</th>
                                  <th className="py-2">Status</th>
                                  <th className="py-2">Payment</th>
                                  <th className="py-2">Date</th>
                                  <th className="py-2">Details</th>
                                </tr>
                              </thead>
                              <tbody>
                                {adminOrders.map(order => (
                                  <React.Fragment key={order.id}>
                                    <tr className="border-t">
                                      <td className="py-2">{order.order_number}</td>
                                      <td className="py-2">{order.customer_name || '—'}</td>
                                      <td className="py-2">{order.customer_phone || '—'}</td>
                                      <td className="py-2">KES {order.total_amount}</td>
                                      <td className="py-2">{order.delivery_method}</td>
                                      <td className="py-2">{order.source || '—'}</td>
                                      <td className="py-2">{order.status || '—'}</td>
                                      <td className="py-2">{order.payment_status || '—'}</td>
                                      <td className="py-2">{order.created_at || '—'}</td>
                                      <td className="py-2">
                                        <button
                                          onClick={() => setAdminExpandedOrders({
                                            ...adminExpandedOrders,
                                            [order.id]: !adminExpandedOrders[order.id]
                                        })}
                                        className="text-blue-600 hover:underline"
                                      >
                                        {adminExpandedOrders[order.id] ? 'Hide' : 'View'}
                                      </button>
                                    </td>
                                  </tr>
                                    {adminExpandedOrders[order.id] && (
                                      <tr className="border-t bg-gray-50">
                                        <td colSpan={10} className="py-3 px-2">
                                          <div className="grid md:grid-cols-2 gap-4">
                                            <div>
                                              <div className="text-xs text-gray-600 mb-2">Items</div>
                                              {order.items && order.items.length > 0 ? (
                                                <ul className="text-sm text-gray-700 space-y-1">
                                                  {order.items.map((item, idx) => (
                                                    <li key={idx}>
                                                      {item.brand} {item.model} ({item.color}) x{item.quantity} — KES {item.total_price}
                                                    </li>
                                                  ))}
                                                </ul>
                                              ) : (
                                                <div className="text-sm text-gray-500">No items</div>
                                              )}
                                            </div>
                                            <div>
                                              <div className="text-xs text-gray-600 mb-2">Update Order Status</div>
                                              <div className="grid sm:grid-cols-2 gap-2 mb-2">
                                                <select
                                                  className="border border-gray-300 rounded-md px-2 py-1 text-sm"
                                                  value={(adminOrderEdits[order.id]?.status) || order.status || 'AWAITING_WHATSAPP'}
                                                  onChange={(e) => setAdminOrderEdits({
                                                    ...adminOrderEdits,
                                                    [order.id]: {
                                                      ...(adminOrderEdits[order.id] || {}),
                                                      status: e.target.value
                                                    }
                                                  })}
                                                >
                                                  <option value="AWAITING_WHATSAPP">AWAITING_WHATSAPP</option>
                                                  <option value="CONFIRMED">CONFIRMED</option>
                                                  <option value="DELIVERED">DELIVERED</option>
                                                  <option value="CANCELLED">CANCELLED</option>
                                                </select>
                                                <select
                                                  className="border border-gray-300 rounded-md px-2 py-1 text-sm"
                                                  value={(adminOrderEdits[order.id]?.payment_status) || order.payment_status || 'UNPAID'}
                                                  onChange={(e) => setAdminOrderEdits({
                                                    ...adminOrderEdits,
                                                    [order.id]: {
                                                      ...(adminOrderEdits[order.id] || {}),
                                                      payment_status: e.target.value
                                                    }
                                                  })}
                                                >
                                                  <option value="UNPAID">UNPAID</option>
                                                  <option value="PAID">PAID</option>
                                                </select>
                                              </div>
                                              <input
                                                type="text"
                                                className="w-full border border-gray-300 rounded-md px-2 py-1 text-sm mb-2"
                                                placeholder="Payment Method (e.g., MPesa, Cash)"
                                                value={(adminOrderEdits[order.id]?.payment_method) || order.payment_method || ''}
                                                onChange={(e) => setAdminOrderEdits({
                                                  ...adminOrderEdits,
                                                  [order.id]: {
                                                    ...(adminOrderEdits[order.id] || {}),
                                                    payment_method: e.target.value
                                                  }
                                                })}
                                              />
                                              <button
                                                onClick={() => handleAdminUpdateOrderStatus(
                                                  order.id,
                                                  (adminOrderEdits[order.id]?.status) || order.status || 'AWAITING_WHATSAPP',
                                                  (adminOrderEdits[order.id]?.payment_status) || order.payment_status || 'UNPAID',
                                                  (adminOrderEdits[order.id]?.payment_method) || order.payment_method || ''
                                                )}
                                                className="bg-black hover:bg-red-600 text-white px-3 py-1.5 rounded-md text-sm font-semibold"
                                              >
                                                Save Order Status
                                              </button>
                                            </div>
                                          </div>
                                        </td>
                                      </tr>
                                    )}
                                  </React.Fragment>
                                ))}
                              </tbody>
                            </table>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </>
            ) : (
              <div className="bg-white rounded-xl p-6 shadow-md text-center">
                <p className="text-gray-600 mb-4">Admin access only.</p>
                <button
                  onClick={() => { setView('store'); window.scrollTo(0, 0); }}
                  className="bg-black hover:bg-red-600 text-white px-6 py-3 rounded-lg font-semibold transition"
                >
                  Back to Store
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {authOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold">
                {authMode === 'register' && 'Create Account'}
                {authMode === 'login' && 'Sign In'}
                {authMode === 'staff' && 'Staff Sign In'}
                {authMode === 'forgot' && 'Forgot Password'}
                {authMode === 'reset' && 'Reset Password'}
                {authMode === 'change' && 'Change Password'}
              </h2>
              <button
                onClick={() => setAuthOpen(false)}
                className="text-gray-500 hover:text-black"
                aria-label="Close"
              >
                X
              </button>
            </div>

            <div className="flex gap-2 mb-6">
              <button
                onClick={() => setAuthMode('login')}
                className={`flex-1 py-2 rounded-lg text-sm font-semibold border ${
                  authMode === 'login' ? 'bg-black text-white border-black' : 'border-gray-200 text-gray-600'
                }`}
              >
                Sign In
              </button>
              <button
                onClick={() => setAuthMode('register')}
                className={`flex-1 py-2 rounded-lg text-sm font-semibold border ${
                  authMode === 'register' ? 'bg-black text-white border-black' : 'border-gray-200 text-gray-600'
                }`}
              >
                Register
              </button>
              <button
                onClick={() => setAuthMode('staff')}
                className={`flex-1 py-2 rounded-lg text-sm font-semibold border ${
                  authMode === 'staff' ? 'bg-black text-white border-black' : 'border-gray-200 text-gray-600'
                }`}
              >
                Staff
              </button>
            </div>

            <form onSubmit={handleAuthSubmit} className="space-y-4">
              {authMode === 'register' && (
                <input
                  type="text"
                  placeholder="Full Name"
                  value={authForm.name}
                  onChange={(e) => setAuthForm({ ...authForm, name: e.target.value })}
                  className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
                  required
                />
              )}

                {(authMode === 'login' || authMode === 'register' || authMode === 'forgot') && (
                  <input
                    type="text"
                    placeholder={authMode === 'forgot' ? 'Email or Phone' : 'Email'}
                    value={authForm.email}
                    onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
                    className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
                    required
                  />
                )}

              {authMode === 'staff' && (
                <input
                  type="text"
                  placeholder="Staff Username"
                  value={authForm.email}
                  onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
                  className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
                  required
                />
              )}

                {authMode === 'register' && (
                  <input
                    type="tel"
                    placeholder="Phone"
                    value={authForm.phone}
                    onChange={(e) => setAuthForm({ ...authForm, phone: e.target.value })}
                    className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
                    required
                  />
                )}

              {(authMode === 'login' || authMode === 'register' || authMode === 'reset' || authMode === 'change' || authMode === 'staff') && (
                <input
                  type="password"
                  placeholder={authMode === 'reset' || authMode === 'change' ? 'New Password' : 'Password'}
                  value={authForm.password}
                  onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
                  className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
                  required
                />
              )}

              {(authMode === 'register' || authMode === 'reset') && (
                <input
                  type="password"
                  placeholder="Confirm Password"
                  value={authForm.confirmPassword}
                  onChange={(e) => setAuthForm({ ...authForm, confirmPassword: e.target.value })}
                  className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
                  required
                />
              )}

              {authMode === 'change' && (
                <>
                  <input
                    type="password"
                    placeholder="Current Password"
                    value={authForm.currentPassword}
                    onChange={(e) => setAuthForm({ ...authForm, currentPassword: e.target.value })}
                    className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
                    required
                  />
                  <input
                    type="password"
                    placeholder="Confirm New Password"
                    value={authForm.confirmPassword}
                    onChange={(e) => setAuthForm({ ...authForm, confirmPassword: e.target.value })}
                    className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
                    required
                  />
                </>
              )}

              {authMode === 'reset' && (
                <input
                  type="text"
                  placeholder="Reset Token"
                  value={authForm.resetToken}
                  onChange={(e) => setAuthForm({ ...authForm, resetToken: e.target.value })}
                  className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
                  required
                />
              )}

              {authError && <p className="text-sm text-red-600">{authError}</p>}
              {authNotice && <p className="text-sm text-green-700">{authNotice}</p>}

              <button
                type="submit"
                disabled={authLoading}
                className="w-full bg-red-600 hover:bg-red-700 text-white py-3 rounded-lg font-bold transition"
              >
                {authLoading ? 'Please wait...' : (
                  authMode === 'register' ? 'Create Account' :
                  authMode === 'login' ? 'Sign In' :
                  authMode === 'staff' ? 'Staff Sign In' :
                  authMode === 'forgot' ? 'Send Reset Instructions' :
                  authMode === 'reset' ? 'Reset Password' :
                  'Change Password'
                )}
              </button>

              {authMode === 'login' && (
                <button
                  type="button"
                  onClick={() => setAuthMode('forgot')}
                  className="w-full text-sm text-gray-600 hover:text-black"
                >
                  Forgot password?
                </button>
              )}

              {(authMode === 'forgot' || authMode === 'reset') && (
                <button
                  type="button"
                  onClick={() => setAuthMode('login')}
                  className="w-full text-sm text-gray-600 hover:text-black"
                >
                  Back to sign in
                </button>
              )}
            </form>
          </div>
        </div>
      )}

      {/* Footer - Matching Screenshot 4 Style */}
      <footer className="bg-black text-white mt-20">
        {/* Newsletter Section - Red Background */}
        <div className="bg-red-600 py-12">
          <div className="container mx-auto px-4 text-center">
            <h3 className="text-2xl sm:text-3xl font-bold mb-3">Join 50,000+ Shoe Lovers</h3>
            <p className="text-red-100 mb-6 text-sm sm:text-base">Get exclusive discounts and early access</p>
            <div className="max-w-md mx-auto flex gap-3">
              <input 
                type="email" 
                placeholder="Enter your email" 
                value={newsletterEmail}
                onChange={(e) => setNewsletterEmail(e.target.value)}
                className="flex-1 px-4 py-3 rounded-lg text-black outline-none text-sm"
              />
              <button 
                onClick={() => {
                  if (newsletterEmail) {
                    alert('Thanks for subscribing! 🎉');
                    setNewsletterEmail('');
                  }
                }}
                className="bg-black hover:bg-gray-900 text-white px-6 sm:px-8 py-3 rounded-lg font-semibold text-sm"
              >
                Subscribe
              </button>
            </div>
          </div>
        </div>

        {/* Blog Section - Best between newsletter and footer */}
        <div id="blog-section" className="bg-gray-950 py-12 border-t border-gray-800">
          <div className="container mx-auto px-4">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-2xl sm:text-3xl font-bold">Latest From Our Blog</h3>
                <p className="text-gray-400 text-sm mt-1">Style tips, drops, and product highlights</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 mb-6">
              <button
                onClick={() => { setBlogCategory('All'); setBlogPage(0); }}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${
                  blogCategory === 'All' ? 'bg-red-600 border-red-600 text-white' : 'border-gray-700 text-gray-300 hover:border-red-600'
                }`}
              >
                All
              </button>
              {blogCategories.map(cat => (
                <button
                  key={cat}
                  onClick={() => { setBlogCategory(cat); setBlogPage(0); }}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${
                    blogCategory === cat ? 'bg-red-600 border-red-600 text-white' : 'border-gray-700 text-gray-300 hover:border-red-600'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
            {blogPosts.length === 0 ? (
              <div className="text-gray-500 text-sm">No blog posts yet.</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {blogPosts.map(post => (
                  <div
                    key={post.id}
                    className="bg-black/60 border border-gray-800 rounded-xl overflow-hidden cursor-pointer hover:border-red-600 transition"
                    onClick={() => { setSelectedBlog(post); setView('blog'); window.scrollTo(0, 0); }}
                  >
                    <div className="aspect-[4/3] bg-gray-900">
                      {post.image_url ? (
                        <img
                          src={`${API_BASE_URL}${post.image_url}`}
                          alt={post.title}
                          className="w-full h-full object-cover"
                          onError={(e) => { e.target.style.display = 'none'; }}
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-500 text-sm">
                          Image placeholder
                        </div>
                      )}
                    </div>
                    <div className="p-4">
                      <div className="text-xs text-gray-500 mb-2">{post.created_at}</div>
                      <h4 className="font-semibold text-white mb-2">{post.title}</h4>
                      <p className="text-sm text-gray-400 line-clamp-3">{post.excerpt || post.content}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-6 flex items-center gap-3">
              <button
                onClick={() => setBlogPage(prev => Math.max(prev - 1, 0))}
                className="px-4 py-2 rounded-lg border border-gray-700 text-gray-300 hover:border-red-600"
                disabled={blogPage === 0}
              >
                Prev
              </button>
              <button
                onClick={() => setBlogPage(prev => prev + 1)}
                className="px-4 py-2 rounded-lg border border-gray-700 text-gray-300 hover:border-red-600"
                disabled={blogPosts.length < blogPageSize}
              >
                Next
              </button>
            </div>
          </div>
        </div>

        {/* Main Footer Content */}
        <div className="container mx-auto px-4 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
            {/* Company Column */}
            <div>
              <h4 className="font-bold mb-4 text-base uppercase tracking-wider">Company</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><button type="button" onClick={() => { setView('about'); window.scrollTo(0, 0); }} className="hover:text-white transition">About Us</button></li>
                <li><button type="button" onClick={() => { setView('locations'); window.scrollTo(0, 0); }} className="hover:text-white transition">Locations</button></li>
                <li><button type="button" onClick={() => { setView('career'); window.scrollTo(0, 0); }} className="hover:text-white transition">Career</button></li>
              </ul>
            </div>

            {/* Resources Column */}
            <div>
              <h4 className="font-bold mb-4 text-base uppercase tracking-wider">Resources</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><button type="button" onClick={() => { setView('privacy'); window.scrollTo(0, 0); }} className="hover:text-white transition">Privacy Policy</button></li>
                <li><button type="button" onClick={() => { setView('refund'); window.scrollTo(0, 0); }} className="hover:text-white transition">Refund Policy</button></li>
                <li><button type="button" onClick={() => { setView('terms'); window.scrollTo(0, 0); }} className="hover:text-white transition">Terms of Service</button></li>
                <li><button type="button" onClick={() => { setView('shipping'); window.scrollTo(0, 0); }} className="hover:text-white transition">Shipping Policy</button></li>
              </ul>
            </div>

            {/* Socials Column */}
            <div>
              <h4 className="font-bold mb-4 text-base uppercase tracking-wider">Socials</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><a href="https://www.facebook.com/people/Shoes-Nexus-Kenya/61566514036190/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition">Facebook</a></li>
                <li><a href="https://www.instagram.com/shoesnexuskenya/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition">Instagram</a></li>
                <li><a href="https://x.com/ShoeNexus" target="_blank" rel="noopener noreferrer" className="hover:text-white transition">Twitter</a></li>
                <li><a href="https://www.tiktok.com/@shoesnexus" target="_blank" rel="noopener noreferrer" className="hover:text-white transition">Tiktok</a></li>
                <li><a href="#" className="hover:text-white transition">Youtube</a></li>
              </ul>
            </div>

            {/* Contact Column */}
            <div>
              <h4 className="font-bold mb-4 text-base uppercase tracking-wider">Contact</h4>
              <div className="space-y-3 text-sm text-gray-400">
                <p className="flex items-center space-x-2">
                  <Phone size={16} className="flex-shrink-0" />
                  <span>{settings?.phone || '+254 748 921 804'}</span>
                </p>
                <div className="flex items-start space-x-2">
                  <MapPin size={16} className="mt-1 flex-shrink-0" />
                  <div>
                    <p>Dynamic Mall, Shop ML55</p>
                    <p>Tom Mboya Street, Nairobi</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Bar */}
          <div className="border-t border-gray-800 pt-8 pb-4">
            <div className="flex flex-col sm:flex-row justify-between items-center gap-4 text-xs sm:text-sm text-gray-400">
              <p>© 2026 Shoes Nexus Kenya, Since 2021. All rights reserved.</p>
              <div className="flex items-center space-x-4">
                <span className="flex items-center space-x-2">
                  <Check size={16} className="text-green-500" />
                  <span>AUTHORIZED RETAILER</span>
                </span>
                <span className="flex items-center space-x-2">
                  <Star size={16} className="text-yellow-500 fill-current" />
                  <span>AUTHENTICITY GUARANTEED</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </footer>

      {/* WhatsApp Floating Button */}
      <a 
        href="https://wa.me/254748921804?text=Hi%20Shoes%20Nexus!%20I'm%20interested%20in%20your%20products"
        target="_blank"
        rel="noopener noreferrer"
        className="fixed bottom-6 right-6 z-50 bg-green-500 hover:bg-green-600 text-white rounded-full p-4 shadow-2xl transition-all transform hover:scale-110 group"
      >
        <svg className="w-7 h-7 sm:w-8 sm:h-8" fill="currentColor" viewBox="0 0 24 24">
          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
        </svg>
        <span className="absolute right-full mr-3 bg-white text-black px-3 py-2 rounded-lg text-xs sm:text-sm font-semibold whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity shadow-lg hidden sm:block">
          Chat with us!
        </span>
        <span className="absolute -top-2 -right-2 bg-red-600 text-white text-xs w-5 h-5 rounded-full flex items-center justify-center">1</span>
      </a>

      {/* Floating Sale Button */}
      <FloatingSaleButton />
    </div>
  );
}

// Checkout Component
  function CheckoutView({ cart, deliveryZones, settings, onSubmit, onBack }) {
    const [formData, setFormData] = useState({
      name: '',
      phone: '',
      email: '',
      address: '',
      notes: '',
      source: 'Website'
    });
  const [selectedZone, setSelectedZone] = useState(deliveryZones[0]?.name || '');

  const getCartTotal = () => cart.reduce((total, item) => total + (item.price * item.quantity), 0);
  const getDeliveryCost = () => {
    const zone = deliveryZones.find(z => z.name === selectedZone);
    return typeof zone?.cost === 'number' ? zone.cost : 200;
  };
  const getTotal = () => getCartTotal() + getDeliveryCost();

    const handleSubmit = () => {
      if (!formData.name || !formData.phone || !formData.address) {
        alert('Please fill in all required fields');
        return;
      }
      onSubmit(formData, selectedZone);
    };

  return (
    <div className="container mx-auto px-4 py-12">
      <h1 className="text-3xl sm:text-4xl font-bold mb-8">Checkout</h1>

      <div className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-xl p-6 shadow-md">
            <h2 className="text-xl font-bold mb-6">Contact Information</h2>
            <div className="space-y-4">
              <input 
                type="text"
                placeholder="Full Name *"
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
              />
              <input 
                type="tel"
                placeholder="Phone Number (M-Pesa) *"
                value={formData.phone}
                onChange={(e) => setFormData({...formData, phone: e.target.value})}
                className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
              />
              <input 
                type="email"
                placeholder="Email (optional)"
                value={formData.email}
                onChange={(e) => setFormData({...formData, email: e.target.value})}
                className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
              />
              <textarea 
                placeholder="Delivery Address *"
                value={formData.address}
                onChange={(e) => setFormData({...formData, address: e.target.value})}
                rows={3}
                className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
              />
                <textarea 
                  placeholder="Order Notes (optional)"
                  value={formData.notes}
                  onChange={(e) => setFormData({...formData, notes: e.target.value})}
                  rows={2}
                  className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
                />
                <label className="text-sm text-gray-600">How did you find us? (Optional)</label>
                <select
                  value={formData.source}
                  onChange={(e) => setFormData({...formData, source: e.target.value})}
                  className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-black outline-none"
                >
                  <option>Website</option>
                  <option>Instagram</option>
                  <option>TikTok</option>
                  <option>Twitter</option>
                  <option>In-store Walkins</option>
                  <option>Referral</option>
                  <option>Other</option>
                  <option>Prefer not to say</option>
                </select>
            </div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-md">
            <h2 className="text-xl font-bold mb-6">Delivery Options</h2>
            <div className="space-y-3">
              {deliveryZones.map(zone => (
                <label 
                  key={zone.name}
                  className={`flex items-center p-4 border-2 rounded-lg cursor-pointer transition ${
                    selectedZone === zone.name ? 'border-black bg-gray-50' : 'border-gray-200 hover:border-gray-400'
                  }`}
                >
                  <input 
                    type="radio"
                    name="delivery"
                    value={zone.name}
                    checked={selectedZone === zone.name}
                    onChange={(e) => setSelectedZone(e.target.value)}
                    className="mr-4"
                  />
                  <div className="flex-1">
                    <div className="font-semibold">{zone.name}</div>
                    <div className="text-sm text-gray-600">{zone.days}</div>
                  </div>
                  <div className="font-bold">
                    KES {typeof zone.cost === 'number' ? zone.cost.toLocaleString() : zone.cost}
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl p-6 shadow-md sticky top-24">
            <h2 className="text-xl font-bold mb-6">Order Summary</h2>
            
            <div className="space-y-3 mb-6 max-h-64 overflow-y-auto">
              {cart.map(item => (
                <div key={item.id} className="flex justify-between text-sm pb-3 border-b">
                  <div className="flex-1">
                    <div className="font-medium">{getPublicTitle(item.product)}</div>
                    <div className="text-xs text-gray-600">Size {item.size} × {item.quantity}</div>
                  </div>
                  <span className="font-semibold">KES {(item.price * item.quantity).toLocaleString()}</span>
                </div>
              ))}
            </div>
            
            <div className="border-t pt-4 space-y-3 mb-6">
              <div className="flex justify-between">
                <span className="text-gray-600">Subtotal</span>
                <span className="font-semibold">KES {getCartTotal().toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Delivery</span>
                <span className="font-semibold">KES {getDeliveryCost().toLocaleString()}</span>
              </div>
            </div>
            
            <div className="border-t pt-4 mb-6">
              <div className="flex justify-between text-lg">
                <span className="font-bold">Total</span>
                <span className="font-bold text-red-600">KES {getTotal().toLocaleString()}</span>
              </div>
            </div>

            <div className="bg-gray-50 p-4 rounded-lg mb-4">
              <div className="font-semibold mb-2">💳 M-Pesa Payment</div>
              <div className="text-sm text-gray-600">
                <p>Paybill: {settings?.mpesa_paybill || '522533'}</p>
                <p>Account: {settings?.mpesa_account || '7776553'}</p>
              </div>
            </div>

            <button 
              onClick={handleSubmit}
              className="w-full bg-black hover:bg-red-600 text-white py-4 rounded-lg font-bold transition-all transform hover:scale-105 mb-3"
            >
              Place Order
            </button>

            <button 
              onClick={onBack}
              className="w-full border-2 border-gray-200 hover:border-black py-3 rounded-lg font-semibold transition"
            >
              Back to Cart
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}







