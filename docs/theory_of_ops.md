
# DV Flow CMake
- DV Flow Integration layer for CMake 
- Define CMake targets based on DV Flow tasks
- Load content defined in flow.dv files

CMake is a Makefile generator. As part of its work of setting up
dependencies, it can setup a task graph. CMake functions build
up structured data to be used by the 

CMake is our 'static' pre-execution evaluation. It's used to 
generate the Makefile that implements static task graph

The commands executed by the Makefile are calls to the task
execution wrapper that takes a concrete set of arguments
and runs the corresponding Python task
- Combine inputs
- Pass parameters (determined during loading)
  - Pass values to a wrapper
  - Returns back the parameters string or errors

Task definition
- input paths
- output path
- parameters string

Each cmake task adds content to the cache directory
- Each type description is written 
- Each task is registered with its inputs, outputs, directory, parameters, and needs
- Each override is added individually
- Each generation task reads appropriate files from the cache directory
  in order to make its decisions
