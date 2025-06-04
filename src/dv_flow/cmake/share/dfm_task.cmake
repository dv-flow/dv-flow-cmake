#****************************************************************************
#* dfm_task.cmake
#****************************************************************************
function(DFM_INIT)
    if (NOT DEFINED DFM)
        if ( DEFINED DFM_PYTHON )
            set(DFM "${DFM_PYTHON} -m dv_flow.mgr" PARENT_SCOPE)
        else()
            message(STATUS "DFM is not defined. Setting to default value.")
            if (EXISTS directory="${CMAKE_SOURCE_DIR}/packages")
                set(DFM "${CMAKE_SOURCE_DIR}/packages/python/bin/python -m dv_flow.mgr")
            else()
                message(FATAL_ERROR "DFM is not defined and no default path found. Please set DFM_PYTHON to the path of the dfm.py script.")
            endif()
        endif()
    endif()
    set(ENV{DFM} "${DFM}")
endfunction()

function(dfm_task name type)
  set(one_value_arguments
#    TYPE
     DESC
  )

  set(multi_value_arguments
    NEEDS
    WITH
  )

  cmake_parse_arguments(ARG "" "${one_value_arguments}"
      "${multi_value_arguments}" ${ARGN})

  if( NOT DEFINED DFM  )
      message(FATAL_ERROR "DFM is not defined. Please call DFM_INIT() before using dfm_task.")
  endif()

#    message("NEEDS: ${ARG_NEEDS}")
    set(needs "")
    set(need_files "")
    foreach( need ${ARG_NEEDS} )
#       message("Need: ${need}") 
#       list(APPEND needs "${need}.json")
       list(APPEND needs ${need})
       get_property(target_location TARGET ${need} PROPERTY OUTPUT)
       list(APPEND need_files "${target_location}")
#       message("Path: ${target_location}")
       get_property(target_depends TARGET ${need} PROPERTY DEPENDS)
#       message("Path Depends: ${target_depends}")
    endforeach()

    string(REPLACE "\"" "\\\"" with_val "${ARG_WITH}")

    make_directory(${CMAKE_CURRENT_BINARY_DIR}/run.${name})
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/run.${name}/${name}.params.json" 
      "{\"name\":\"${name}\", 
        \"package\":\"${CMAKE_PROJECT_NAME}\",
        \"rundir\":\"${CMAKE_CURRENT_BINARY_DIR}/run.${name}\",
        \"srcdir\":\"${CMAKE_CURRENT_SOURCE_DIR}\",
        \"type\":\"${type}\",
        \"with\":\"${with_val}\",
        \"needs\":\"${need_files}\",
        \"desc\":\"\"
        }"
    )

    execute_process(
        COMMAND ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/dfm_util cmake-mk-run-spec 
          ${CMAKE_CURRENT_BINARY_DIR}/run.${name}/${name}.params.json
          -o ${CMAKE_CURRENT_BINARY_DIR}/${name}.run-spec.json
         RESULT_VARIABLE config_code
#         COMMAND_ECHO STDOUT
    )
    if( NOT config_code EQUAL 0 )
        message(FATAL_ERROR "Configuration failed with code ${config_code} (${DFM} mk_run_spec)")
    endif()

#    execute_process(
#      COMMAND foo.bar
#    )
#      COMMAND echo "{1}" > "${name}.json"
#      COMMAND ${CMAKE_SOURCE_DIR}/runit.sh 
#      COMMAND echo "{2}" > "${name}.json"
#      RESULT_VARIABLE result
#      OUTPUT_VARIABLE output
#      ERROR_VARIABLE error_output
#    )

#        --with "${ARG_WITH}"
#     add_custom_command(
#       OUTPUT "${name}.run-spec.json"
# #      COMMENT "Creating DFM task config ${name} with type ${type}"
#       COMMAND ${DFM} util cmake-mk-run-spec 
#         ${CMAKE_CURRENT_BINARY_DIR}/${name}.params.json
#         -o ${name}.run-spec.json
# #      COMMAND mkdir -p `dirname "${name}.json"`
# #      COMMAND touch "${name}.json"
#     )
#     add_custom_target(${name}-run-spec
#       DEPENDS "${name}.run-spec.json"
#       WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
# #      COMMENT "Creating DFM task ${name}"
#     )

    message("Task: ${name} ${ARG_TARGET} ${needs}")
#  message("Registering task ${name} depends on ${inputs}")
    add_custom_command(
      OUTPUT "${name}.d"
      DEPENDS ${needs} 
#      COMMENT "Running DFM task ${name} with type ${type}"
#      COMMAND echo "Hi: ${name}.json \"${need_files}\""
      COMMAND ${DFM} util cmake-run-spec 
        ${CMAKE_CURRENT_BINARY_DIR}/${name}.run-spec.json
        --status ${CMAKE_CURRENT_BINARY_DIR}/${name}.d
      WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/run.${name}
#      COMMAND mkdir -p `dirname "${name}.json"`
#      COMMAND touch "${name}.json"
    )
    add_custom_target(${name} 
      DEPENDS "${name}.d" 
      WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
#      COMMENT "Running DFM task ${name}"
    )

#    get_target_property(target_location ${name} LOCATION)
    get_property(target_location TARGET ${name} PROPERTY LOCATION)
#    message("Target: ${target_location}")
    set_target_properties(${name} PROPERTIES OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/run.${name}/${name}.json")
    set_target_properties(${name} PROPERTIES DEPENDS "${needs}")

endfunction()


