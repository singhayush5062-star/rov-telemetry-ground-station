TECHNICAL ASSESSMENT

ROV Telemetry Ground Station

Build  one  native  desktop  application  that  simulates  a  small  underwater vehicle and lets an operator monitor
and control it.

Application requirements

•  Simulate  movement  forward,  sideways,  up/down,  and  turning,  including  simple  drag  and  a  short

thruster-response delay.

•  Display live armed state, mode, roll, pitch, yaw, depth, and battery voltage.
•  Provide Arm/Disarm controls and Manual, Depth Hold, and Heading Hold modes.
•
•

In Manual mode, accept keyboard or joystick controls.
In  Depth  Hold  and  Heading  Hold  modes,  let  the  operator  set  a  target  depth  or  heading; the holding
method is your choice.

•  Safety: thrust must be zero whenever disarmed. In Manual mode, return thrust to zero after one second

without operator input.

•  Display a live depth-versus-time plot and an OpenStreetMap view inside the application.
•  Keep the application responsive during simulation and interface updates.

Video walkthrough application display only

•  Show the main desktop application window and dashboard layout.
•  Display sample or simulated values for armed state, mode, roll, pitch, yaw, depth, and battery voltage.
•  Show the Arm/Disarm controls, Manual / Depth Hold / Heading Hold modes, and target depth/heading

inputs.

•  Show the depth-versus-time plot with sample or simulated data and the OpenStreetMap view.
•  The recording is an interface walkthrough only. Working movement, hold modes, and safety responses
do not need to be demonstrated in the video; be ready to explain your implementation at interview.

Rules and technical guidance

•  C++ with Qt/QML is preferred. Python or another suitable desktop language is acceptable. Do not build

a browser or web application.

•  No  hardware  is  required.  Simple  simulated  or  sample  data  (e.g.,  depth,  heading, orientation, battery
voltage) may be generated directly in the application. SITL, MAVLink, ROS, or similar frameworks are
optional and give no extra advantage.

•  AI coding tools are permitted; disclose which were used and how in the README.
•  You must be able to explain and modify every part of the implementation during the interview.
•  Prefer a smaller, reliable implementation over an incomplete feature set.
•  Optional extras: CSV logging, simulated water current, or unit tests.

Coratia Technologies Pvt. Ltd.  •  Software Internship Technical Assessment

